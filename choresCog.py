import discord
import sqlalchemy.orm
import sqlalchemy.exc
import random
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.expression import or_
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from discord.ext.commands import Cog

from lib.util import parse_args, sync_time
from orm.tables import Chore, Person, Assignment


async def param_none_error_check(ctx: discord.ext.commands.context,
                                 params: dict,
                                 param: str,
                                 msg: str = "") -> bool:
    if msg == "":
        msg = str.format("Missing parameter %s. <@!190676919212179456>, give this error a real message.", param)
    try:
        if params[param] is None:
            await ctx.send(content=msg)
            return True
    except KeyError:
        await ctx.send(content=msg)
        return True

    return False


class ChoresCog(Cog):
    def __init__(self, bot: commands.bot, session: sqlalchemy.orm.Session):
        self.index = 0
        self.bot = bot
        # self.channel = self.bot.get_channel(channel)
        self.session = session
        self.assign_chore.start()
        self.chore_reminder.start()

    @tasks.loop(hours=1)
    async def check_loops(self):
        if self.assign_chore.failed():
            self.assign_chore.restart()
            print("Restarting assign_chore loop due to failure!")
        if self.chore_reminder.failed():
            self.chore_reminder.restart()
            print("Restarting chore_reminder loop due to failure!")

    @tasks.loop(minutes=10)
    async def assign_chore(self):
        await self.bot.wait_until_ready()

        print("Running assign_chore loop.")

        a: Assignment = sqlalchemy.orm.aliased(Assignment)  # Alias Assignment table to 'a'

        # Query finds all chores, outer joining most recent Assignment of that chore.
        # Should allow us to check if a chore is due for reassignment.
        '''
        Query: 
        select * from chores 
        left outer join assignments a on a.chore_id = chores.id
        where
            a.id = (select max(b.id) from assignments b where b.chore_id = a.chore_id)
            or 
            a.id is null
        '''
        chore_assignment_unique = self.session.query(Chore, a).join(a, isouter=True).filter(
            or_(
                a.id == self.session.query(func.max(Assignment.id)).filter(
                    Assignment.chore_id == a.chore_id
                ),
                a.id.is_(None)
            )
        )

        # for each row returned in prior query
        for row in chore_assignment_unique:
            chore: Chore = row[0]
            assignment: Assignment = row[1]
            next_person: Person = Person()
            channel = self.bot.get_channel(int(chore.channel))

            # check for chore frequency last chore completion to be long enough ago that it's past the freq.
            if assignment is not None and \
                    assignment.completionDate is not None and \
                    assignment.completionDate <= (datetime.utcnow() - timedelta(days=chore.frequency)):
                #     Recorded completion  before or on       now   - (frequency) days

                if len(chore.validPersons) == 1:
                    next_person = chore.validPersons[0]
                else:
                    persons = []
                    # create a list of people who can do this chore.
                    for p in chore.validPersons:
                        persons.append(p.id)

                    # choose the next person to do the chore. The person should rotate so assignment is even.
                    '''
                    query:
                    
                    select *
                    from chores c
                    left join assignments a on c.id = a.chore_id 
                    where
                          c.id = \\chore we're looking at\\
                          and a.completedBy_id is not null
                    order by a.id desc
                    limit \\number of valid people, minus 1\\
                    '''
                    # noinspection PyComparisonWithNone
                    last_persons_ids: list = self.session.query(Chore, a).outerjoin(a, a.chore_id == Chore.id).filter(
                            Chore.id == assignment.chore_id,
                            a.completedBy != None
                        ).order_by(a.id.desc()).limit(len(persons) - 1).all()

                    # choose the next person to do the chore. Make sure to exclude last person who did it.
                    '''
                    query:
                    select * from person p where
                        p.id in (\\external list of valid persons\\) 
                        and
                        p.id != \\prior assignment\\.person.id
                    '''
                    next_person_ls: list = self.session.query(Person).filter(
                        Person.id.notin_(last_persons_ids)
                    ).all()
                    next_person_index = random.randint(0, len(next_person_ls) - 1)
                    next_person = next_person[next_person_index]

            elif assignment is None:
                # in this case, create a list of all people who can do this chore
                persons = []
                for p in chore.validPersons:
                    persons.append(p.id)
                # choose who will do this chore next
                next_person_ls: list = self.session.query(Person).filter(Person.id.in_(persons)).all()
                next_person_index = random.randint(0, len(next_person_ls) - 1)
                next_person = next_person[next_person_index]

            # if there is no next person, pass this loop
            if next_person.name is None:
                continue

            # create a new assignment
            new_assignment = Assignment()
            new_assignment.person = next_person
            new_assignment.chore = chore
            new_assignment.completionDate = None
            new_assignment.lastReminder = datetime.utcnow()
            new_assignment.assignmentDate = datetime.utcnow()

            # Add the new assignment to the database.
            try:
                self.session.add(new_assignment)
                self.session.commit()
            except sqlalchemy.exc.SQLAlchemyError as e:
                # This will normally indicate a system error like the SQL server not running.
                await channel.send(
                    content="Big error, very scary. Couldn't assign a chore!"
                            "\r\n"
                            "Chore: " + str(chore.choreName) + "\r\n"
                                                               "Person: " + next_person.name +
                            "Please DM this error to Abir Vandergriff#6507 so he can fix it!")
                await channel.send(content=e)
                continue
            # Notify the person of their chore assignment.
            await channel.send(
                content="Hey, " +
                        str(new_assignment.person.name) +
                        " you have been assigned to do " +
                        new_assignment.chore.choreName +
                        " (ID: " +
                        str(new_assignment.chore_id) +
                        ")")

        await sync_time(10, "assign_chore")

    @tasks.loop(minutes=10)
    async def chore_reminder(self):
        await self.bot.wait_until_ready()

        print("Running chore_reminder loop.")

        q = self.session.query(Assignment).filter(
            Assignment.assignmentDate <= datetime.utcnow(),
            Assignment.completionDate.is_(None)
        ).all()
        for assignment in q:
            channel = self.bot.get_channel(int(assignment.chore.channel))

            if assignment.lastReminder <= datetime.utcnow() - timedelta(days=assignment.chore.frequency):
                # send reminder
                await channel.send(content=str(assignment.person.name) +
                                   "! Remember, you have to \"" +
                                   assignment.chore.choreName +
                                   "\" (ID: " +
                                   str(assignment.chore_id) +
                                   ")!"
                                   )
                # Save the reminder
                assignment.lastReminder = datetime.utcnow()
                self.session.commit()

        await sync_time(10, "chore_reminder")

    @commands.command(name='alive', description='Ask if H.E.L.P.eR. is alive.', aliases=['test'])
    async def c_test(self, ctx: discord.ext.commands.Context):
        print("Cog test received, sending message.")
        message = f'I\'m alive {ctx.message.author.mention}.'
        await ctx.message.channel.send(content=message)

    @commands.command(name='new_chore', description="Add a new chore.", aliases=['new'],
                      help="Must have parameters:\r\n"
                           "-chore={choreName} : "
                           "The title or name of the chore you're adding. It can be as simple"
                           "or complex as you want, and doesn't have to be unique.\r\n"
                           "-valid people={Tags for people} : "
                           "Tag the people who can do this chore. Seperate with commas. "
                           "For example; 'valid people=@Shel, @Emma, @Mariah, @Nathan "
                           "Please do not tag @Everyone! \r\n"
                           "-frequency={Integer number} : "
                           "How often the chore needs done, in days.\r\n"
                           "Optional parameter: \r\n"
                           "-desc={description of chore} : "
                           "For more complex chores, give a description so the assignee "
                           "knows how to do it! \r\n",
                      usage="-chore={choreName} "
                            "-valid people=@{person1}, @{person2} "
                            "-frequency={frequency in days} "
                            "(-desc={chore description})")
    async def new_chore(self, ctx: discord.ext.commands.Context):
        channel: discord.ext.commands.Context.channel = ctx.message.channel

        params: dict = parse_args(  # Parse command args into a dictionary
            # Content of command, with actual command stripped.
            ctx.message.content[len(ctx.invoked_with) + 1:].lstrip())  # Strip leading spaces just in case.

        err = False
        if await param_none_error_check(ctx, params, 'chore',
                                        "You have to give me a name for the new chore! "
                                        "(Hint: add -chore={choreName} to your message)") \
                and not err:
            err = True

        if await param_none_error_check(ctx, params, 'valid people',
                                        "You have to give me people who can do this chore! "
                                        "Remember to seperate people with commas! "
                                        "(Hint: add '-valid people={Tags for people}'") \
                and not err:
            err = True

        if await param_none_error_check(ctx, params, 'frequency',
                                        "You have to tell me how often to assign the chore! "
                                        "(Hint: add -frequency={frequency in days}") \
                and not err:
            err = True

        if err:
            return

        errcheckmsg = "Please give me people as tags so I can notify them when they've been assigned a chore. " \
                      "Also do not tag @Everyone!"
        if isinstance(params['valid people'], list):
            for i in range(len(params['valid people'])):
                if not params['valid people'][i].startswith('<@'):
                    await channel.send(content=errcheckmsg)
                    return
        else:
            if not params['valid people'].startswith('<@!'):
                await channel.send(content=errcheckmsg)
                return

        # Ensure people passed in exist in DB.
        people = []
        try:
            if not isinstance(params['valid people'], list):
                person = Person()
                person.name = params['valid people']
                people.append(self.query_and_add_person(person))
            else:
                for i in range(len(params['valid people'])):
                    person = Person()
                    person.name = params['valid people'][i]
                    people.append(self.query_and_add_person(person))
        except sqlalchemy.exc.SQLAlchemyError:
            await channel.send("Something went wrong! Couldn't validate tagged people for database!")
            return

        chore = Chore()
        chore.choreName = params['chore']
        try:
            chore.desc = params['desc']
        except KeyError:
            print("No Desc given")
        chore.validPersons = people
        chore.frequency = params['frequency']
        chore.channel = channel.id
        try:
            self.session.add(chore)
            self.session.commit()
        except sqlalchemy.exc.SQLAlchemyError:
            await channel.send("Something went wrong!")
            return
        await channel.send("Successfully added Chore!")

    @commands.command(name='finished_chore',
                      description="Mark a chore as complete.",
                      aliases=['done', 'complete', 'finished'],
                      usage="{chore assignment id} \r\n"
                            " or \r\n"
                            "!finished_chore -name={exact chore name} \r\n"
                            "Note: only use -name flag if the name is unique!")
    async def finished_chore(self, ctx: discord.ext.commands.Context):
        param = ctx.message.content[len(ctx.invoked_with) + 1:].lstrip()
        sender = ctx.author.mention

        if param.find('-') == -1:
            try:
                param = int(param)
            except ValueError:
                await ctx.message.channel.send(content="Improper usage of this command! "
                                                       "Please use '!help finished_chore' "
                                                       "for instructions.")
                return

            q: list = self.session.query(Assignment).filter(
                Assignment.chore_id == param,
                Assignment.completionDate.is_(None)
            ).all()

            if len(q) == 0:
                await ctx.message.channel.send(content="No chore of that ID, or that chore is not currently "
                                                       "assigned!")
                return
            if len(q) > 1:
                # What. This should literally never happen, since the id is a unique primary key.
                await ctx.message.channel.send(
                    content="That ID gave more than one result! This doesn't make sense! \r\n"
                            "Abir Vandergriff#6507 needs learn how to program!"
                            "(Send him a PM for help)")
                raise ValueError
            for assignment in q:
                channel = self.bot.get_channel(int(assignment.chore.channel))

                if channel != ctx.message.channel:
                    await ctx.message.channel.send(content="That ID is not available on this channel!")
                    return

                if sender != assignment.person.name:
                    await channel.send(content="Hey " +
                                               str(assignment.person.name) +
                                               ", make sure to thank " +
                                               str(sender) +
                                               " for doing your chore!")
                person = Person()
                person.name = sender
                q_person = self.query_and_add_person(person)
                assignment.completionDate = datetime.utcnow()
                assignment.completedBy = q_person
                self.session.commit()

                await channel.send(content="Thanks for doing your part, " + str(sender))
        else:
            await ctx.message.channel.send(content="This isn't implemented right now. Use the ID entry instead!")

    @commands.command(hidden=True)
    async def refresh_db(self, ctx):
        self.session.expire_all()
        self.session.close()
        await ctx.message.channel.send(content="Databases have been refreshed. " + ctx.author.mention)

    @commands.command(name="my_active",
                      description="List all of your active chores.",
                      aliases=["mine", "my_unfinished", "my_chores"],
                      help="Get a list of all of your currently unfinished chores")
    async def my_active(self, ctx):
        person = Person()
        person.name = ctx.author.mention
        person = self.query_and_add_person(person)

        active_chores = self.session.query(Assignment).filter(
            Assignment.person == person,
            Assignment.assignmentDate <= datetime.utcnow(),
            Assignment.completionDate.is_(None)
        ).all()

        message = None
        for assignment in active_chores:
            if message:
                message += "\r\n{} (ID: {})".format(assignment.chore.choreName,
                                                    assignment.chore_id)
            else:
                message = "{} (ID: {})".format(assignment.chore.choreName,
                                               assignment.chore_id)

        await ctx.message.channel.send(content=message)

    @commands.command(name="active",
                      description="List all active chores.",
                      aliases=["unfinished", "unfinished_chores"],
                      help="Get a list of all currently unfinished chores")
    async def active(self, ctx):
        active_chores = self.session.query(Assignment).filter(
            Assignment.assignmentDate <= datetime.utcnow(),
            Assignment.completionDate.is_(None)
        ).all()

        message = None
        for assignment in active_chores:
            if message:
                message += "\r\n{} (ID: {}) - assigned to: {}".format(assignment.chore.choreName,
                                                                      assignment.chore_id,
                                                                      assignment.person.name)
            else:
                message = "{} (ID: {}) - assigned to: {}".format(assignment.chore.choreName,
                                                                 assignment.chore_id,
                                                                 assignment.person.name)

        await ctx.message.channel.send(content=message)

    @commands.command(name='change_chore', description="Change an existing chore.", aliases=['change'],
                      help="Must have parameter:\r\n"
                           "{chore id} : Put just after the command. Specifies the chore to change.\r\n"
                           "Optional parameter, although there should be at least one: \r\n"
                           "-chore={choreName} : "
                           "The new title for the chore. It can be as simple"
                           "or complex as you want, and doesn't have to be unique.\r\n"
                           "-valid people={Tags for people} : "
                           "Tag the people who can do this chore. Seperate with commas. This is an inclusive "
                           "list, so if they're not in this list, but they are on the chore, they will be "
                           "removed. "
                           "For example; 'valid people=@Shel, @Emma, @Mariah, @Nathan "
                           "Please do not tag @Everyone! \r\n"
                           "-frequency={Whole number} : "
                           "How often the chore needs done, in days.\r\n"
                           "-desc={description of chore} : "
                           "For more complex chores, give a description so the assignee "
                           "knows how to do it! \r\n",
                      usage="{chore id} "
                            "(-chore name={name to recognize the chore by} "
                            "-valid people=@{person1}, @{person2} "
                            "-frequency={frequency in days} "
                            "-desc={chore description})")
    async def change_chore(self, ctx: discord.ext.commands.Context):
        channel: discord.ext.commands.Context.channel = ctx.message.channel

        command_input = ctx.message.content[len(ctx.invoked_with) + 1:].lstrip()  # Strip leading spaces just in case.

        # We should really have at least one input, otherwise we're just wasting resources.
        if command_input.find('-') == -1:
            await channel.send(content="You haven't told me what to change! Use command '!help change_chore' for "
                                       "info on how to use this command!")
            return

        chore_id = command_input[:command_input.find('-')].lstrip().rstrip()
        command_input = command_input[command_input.find('-'):]

        # Parse command args into a dictionary
        # Content of command, with actual command stripped.
        params: dict = parse_args(
            command_input
        )

        if params.get('chore'):
            params['chore name'] = params['chore']

        if not params.get('chore name') and not params.get('valid people') and not params.get('frequency'):
            await channel.send(content="Your change parameter is wrong! Use command '!help change_chore' for "
                                       "info on how to use this command!")
            return

        chore: Chore = self.session.query(Chore).filter(
            Chore.id == chore_id
        ).one()

        if not chore:
            await channel.send(content="Could not find chore matching that id!")
            return

        if params.get('chore name'):
            chore.choreName = params['chore name']
        if params.get('valid people'):
            errcheckmsg = "Please give me people as tags so I can notify them when they've been assigned a chore. " \
                          "Also do not tag @Everyone!"
            if isinstance(params['valid people'], list):
                for person_tag in range(len(params['valid people'])):
                    if not params['valid people'][person_tag].startswith('<@'):
                        await channel.send(content=errcheckmsg)
                        return
            else:
                if not params['valid people'].startswith('<@!'):
                    await channel.send(content=errcheckmsg)
                    return

            # Ensure people passed in exist in DB.
            people = []
            try:
                if not isinstance(params['valid people'], list):
                    person = Person()
                    person.name = params['valid people']
                    people.append(self.query_and_add_person(person))
                else:
                    for i in range(len(params['valid people'])):
                        person = Person()
                        person.name = params['valid people'][i]
                        people.append(self.query_and_add_person(person))
            except sqlalchemy.exc.SQLAlchemyError:
                await channel.send("Something went wrong! Couldn't validate tagged people for database!")
                return
            chore.validPersons = people
        if params.get('frequency'):
            chore.frequency = params['frequency']
        if params.get('desc'):
            chore.desc = params['desc']

        try:
            self.session.commit()
        except sqlalchemy.exc.SQLAlchemyError:
            await channel.send("Something went wrong!")
            return
        await channel.send(f"Successfully changed Chore {chore_id}!")

    """
    command ideas:
        !delete_chore - This one is necessary. Removed valid people from a chore that didn't need done anymore, and that
            really broke the assignment loop when it came time for it to be assigned again.
        !replace_user - Takes two tag parameters. First one is the one being replaced, second is the replacer.
            Useful for DB maintenance of many chores at once, mostly because Scott took Emma's chores while she was
            away at the treatment facility for her eating disorder.
        !reassign_chore - Reassigns the chore on the same criteria as assign_chore(). Probably just abstract the 
            method at some point in the logic.
        !invite - Respond with the helper invite link. Probably just useful for me.
        !who_has - Takes a chore id, sends a message saying who has it. Probably check against chore names
            if the parameter is a string.
        !chore_settings or !info - Returns the settings of a chore, queried from the database
    """

    def query_and_add_person(self, person: Person):
        try:
            person = self.session.query(Person) \
                .filter(Person.name == person.name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            self.session.add(person)
            self.session.commit()
        return self.session.query(Person).filter(Person.name == person.name).one()

    def refresh_db_internal(self):
        self.session.expire_all()
