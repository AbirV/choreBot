from discord.ext import commands
from choresCog import ChoresCog
from sqlalchemy.orm import sessionmaker
import sqlalchemy.orm
import sqlalchemy

bot = commands.Bot(command_prefix="!")
token = open("resources/APIKey.txt", "r").readline()
channel = int(open("resources/Channel.txt", "r").readline())


@bot.event
async def on_ready():
    # build DB connection
    import ORM.tables as tables
    print("SQLAlchemy Version: {}".format(sqlalchemy.__version__))  # Mostly for debug if necessary

    engine = sqlalchemy.create_engine(open("resources/mysqlEngine.txt", "r").readline(), pool_recycle=3600, echo=False)
    engine.execute("CREATE DATABASE IF NOT EXISTS helper")
    engine.execute("USE helper")

    tables.meta.create_all(bind=engine)

    session_maker = sessionmaker(bind=engine)

    session = session_maker()

    # Add cogs
    bot.add_cog(ChoresCog(bot, channel, session))

    print("H.E.L.P.eR. ready")


bot.run(token)
