import discord
import sqlalchemy.orm
import sqlalchemy.exc
from random import choice
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.expression import or_
from datetime import datetime, timedelta
from asyncio import sleep
from discord.ext import commands
from discord.ext.commands import Cog

from lib.util import parse_args
from ORM.tables import Chore, Person, Assignment


async def param_none_error_check(ctx: discord.ext.commands.context, params: dict, param: str, msg: str = "") -> bool:
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
    def __init__(self, bot: commands.bot, channel, session: sqlalchemy.orm.Session):
        self.index = 0
        self.bot = bot
        self.channel = self.bot.get_channel(channel)
        self.session = session
        bot.loop.create_task(self.assign_chore())
        bot.loop.create_task(self.chore_reminder())

    async def assign_chore(self):
        await self.bot.wait_until_ready()
        session = self.session

        while not self.bot.is_closed():
            # 3600 second sleep for 1 hour
            await sleep(3600)

            a: Assignment = sqlalchemy.orm.aliased(Assignment)  # Alias Assignment table to 'a'

            # Query finds all chores, outer joining most recent Assignment of that chore.
            # Should allow us to check if a chore is due for reassignment.
            '''
            select * from chores 
            left outer join assignments a on a.chore_id = chores.id
            where
                a.id = (select max(b.id) from assignments b where b.chore_id = a.chore_id)
                or 
                a.id is null
            '''
            chore_assignment_unique = session.query(Chore, a).join(a, isouter=True).filter(

                or_(
                    a.id == session.query(func.max(Assignment.id)).filter(
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

                # check for chore frequency last chore completion to be long enough ago that it's past the freq.
                if assignment is not None and \
                        assignment.completionDate is not None and \
                        assignment.completionDate <= (datetime.utcnow() - timedelta(days=chore.frequency)):
                    #     Recorded completion  before or on       now   - (frequency) days

                    persons = []
                    # create a list of people who can do this chore.
                    for p in chore.validPersons:
                        print(p.id)
                        persons.append(p.id)

                    # choose the next person to do the chore. Make sure to exclude last person who did it.
                    '''
                    select * from person p where
                        p.id in (\\external list of valid persons\\) 
                        and
                        p.id != \\prior assignment\\.person.id
                    '''
                    next_person = choice(
                        session.query(Person).filter(
                            Person.id.in_(persons),
                            Person.id != assignment.person_id
                        ).all()
                    )
                elif assignment is None:
                    # in this case, create a list of all people who can do this chore
                    persons = []
                    for p in chore.validPersons:
                        persons.append(p.id)
                    # choose who will do this chore next
                    next_person = choice(session.query(Person).filter(Person.id.in_(persons)).all())

                # if there is no next person, pass this loop
                if next_person.name is None:
                    continue

                # create a new assignment
                new_assignment = Assignment()
                new_assignment.person = next_person
                new_assignment.chore = chore
                new_assignment.completionDate = None

                # Add the new assignment to the database.
                try:
                    session.add(new_assignment)
                    session.commit()
                except sqlalchemy.exc.SQLAlchemyError as e:
                    # This will normally indicate a system error like the SQL server not running.
                    await self.channel.send(
                        content="<@!190676919212179456>! Big error, very scary. Couldn't assign a chore!"
                                "\r\n"
                                "Chore: " + str(chore.choreName) + "\r\n"
                                                                   "Person: " + next_person.name)
                    await self.channel.send(content=e)
                    continue
                # Notify the person of their chore assignment.
                await self.channel.send(
                    content="Hey, " +
                            str(new_assignment.person.name) +
                            " you have been assigned to do " +
                            new_assignment.chore.choreName +
                            " (ID: " +
                            str(new_assignment.id) +
                            ")")

    async def chore_reminder(self):
        await self.bot.wait_until_ready()
        session = self.session

        while not self.bot.is_closed():
            # 3600 second sleep for 1 hour
            await sleep(3600)

            # reminderdate = datetime.utcnow() - timedelta(days=Assignment.chore.frequency)
            q = session.query(Assignment).filter(
                Assignment.assignmentDate <= datetime.utcnow(),
                Assignment.completionDate.is_(None)
            ).all()
            for assignment in q:
                if assignment.lastReminder <= datetime.utcnow() - timedelta(days=assignment.chore.frequency):
                    # send reminder
                    await self.channel.send(content=
                                            str(assignment.person.name) +
                                            "! Remember, you have to do " +
                                            assignment.chore.choreName +
                                            " (ID: " +
                                            str(assignment.chore.id) +
                                            ")!"
                                            )
                    # Save the reminder
                    assignment.lastReminder = datetime.utcnow()
                    session.commit()

    @commands.command(name='alive', description='Ask if H.E.L.P.eR. is alive.', aliases=['test'])
    async def c_test(self, ctx: discord.ext.commands.Context):
        print("Cog test received, sending message.")
        if ctx.message.channel == self.channel:
            message = 'I\'m alive ' + ctx.message.author.mention
            await ctx.send(content=message)
        return

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
        params: dict = parse_args(  # Parse command args into a dictionary
            # Content of command, with actual command stripped.
            ctx.message.content[len(ctx.invoked_with) + 1:].lstrip())  # Strip leading spaces just in case.
        '''
        for key, value in params.items():
            if value is str:
                await ctx.send(content="Key = " + key + " Val = " + value)
            else:
                await ctx.send(content="Key = " + key + " Val = " + str(value))
        '''
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
                    await ctx.send(content=errcheckmsg)
                    return
        else:
            if not params['valid people'].startswith('<@!'):
                await ctx.send(content=errcheckmsg)
                return

        # Ensure people passed in exist in DB.
        person = Person()
        people = []
        try:
            if not isinstance(params['valid people'], list):
                person.name = params['valid people']
                people.append(self.query_and_add_person(person))
            else:
                for i in range(len(params['valid people'])):
                    person = Person()
                    print(params['valid people'][i])
                    person.name = params['valid people'][i]
                    people.append(self.query_and_add_person(person))
        except sqlalchemy.exc.SQLAlchemyError:
            await ctx.send("Something went wrong! Couldn't validate tagged people for database!")
            return

        chore = Chore()
        chore.choreName = params['chore']
        try:
            chore.desc = params['desc']
        except KeyError:
            print("No Desc given")
        chore.validPersons = people
        chore.frequency = params['frequency']
        try:
            self.session.add(chore)
            self.session.commit()
        except sqlalchemy.exc.SQLAlchemyError:
            await ctx.send("Something went wrong!")
            return
        await ctx.send("Successfully added Chore!")

        return

    @commands.command(name='finished_chore',
                      description="Mark a chore as complete.",
                      aliases=['done', 'complete', 'finished'],
                      usage="{chore assignment id} \r\n"
                            " or \r\n"
                            "!finished_chore -name={exact chore name} \r\n"
                            "Note: only use -name flag if the name is unique!")
    async def finished_chore(self, ctx: discord.ext.commands.Context):
        param: str = ctx.message.content[len(ctx.invoked_with) + 1:].lstrip()
        sender = ctx.author.mention

        if param.find('-') == -1:
            try:
                param = int(param)
            except ValueError:
                await ctx.send(content="Improper usage of this command! Please use '!help finished_chore' "
                                       "for instructions.")
                return

            q: list = self.session.query(Assignment).filter(
                Assignment.id == param,
                Assignment.completionDate.is_(None)
            ).all()

            if len(q) == 0:
                await ctx.send(content="No chore of that ID, or that chore is already complete!")
                return
            if len(q) > 1:
                # What. This should literally never happen.
                await ctx.send(content="That ID gave more than one result! This doesn't make sense! \r\n"
                                       "<@!190676919212179456>, learn how to program!")
                return
            for assignment in q:
                if sender != assignment.person.name:
                    await ctx.send(content="Hey " +
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

                await ctx.send(content="Thanks for doing your part, " + str(sender))

    def query_and_add_person(self, person: Person):
        try:
            person = self.session.query(Person) \
                .filter(Person.name == person.name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            self.session.add(person)
            self.session.commit()
        return self.session.query(Person).filter(Person.name == person.name).one()
