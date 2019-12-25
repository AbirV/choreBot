import discord
import sqlalchemy.orm
import sqlalchemy.exc
from asyncio import sleep
from discord.ext import commands
from discord.ext.commands import Cog
from lib.util import parse_args
from ORM.tables import Chore, Person


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

    async def assign_chore(self):
        await self.bot.wait_until_ready()

        print("loop test begun")
        while not self.bot.is_closed():
            # 3600 second sleep for 1 hour
            await sleep(15)
            print("sleep passed")
            # await self.channel.send("sleep test passed.")
            break

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
    async def new_chore(self, ctx):
        params: dict = parse_args(  # Parse command args into a dictionary
            # Content of command, with actual command stripped.
            ctx.message.content[len(ctx.invoked_with) + 1:].lstrip())  # Strip leading spaces just in case.
        for key, value in params.items():
            if value is str:
                await ctx.send(content="Key = " + key + " Val = " + value)
            else:
                await ctx.send(content="Key = " + key + " Val = " + str(value))

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

    def query_and_add_person(self, person: Person):
        try:
            person = self.session.query(Person) \
                .filter(Person.name == person.name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            self.session.add(person)
            self.session.commit()
        return self.session.query(Person).filter(Person.name == person.name).one()
