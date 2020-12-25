from discord.ext import commands
from choresCog import ChoresCog
from sqlalchemy.orm import sessionmaker
import sqlalchemy.orm
import sqlalchemy
import sys

bot = commands.Bot(command_prefix="!")
token = open("resources/APIKey.txt", "r").readline()


@bot.event
async def on_ready():
    # build DB connection
    from orm import tables
    print("SQLAlchemy Version: {}".format(sqlalchemy.__version__))  # Mostly for debug if necessary

    engine = sqlalchemy.create_engine(open("resources/mysqlEngine.txt", "r").readline(), pool_recycle=3600, echo=False)
    engine.execute("CREATE DATABASE IF NOT EXISTS helper")
    for arg in sys.argv:
        if arg == 'testing':
            print("Testing flag set!")
            engine.execute("CREATE DATABASE IF NOT EXISTS helpertest")

    tables.meta.create_all(bind=engine)
    session = (sessionmaker(bind=engine))()

    # Add cogs
    bot.add_cog(ChoresCog(bot, session))

    """
    cog ideas:
        CookbookCog - Stores recipes as ingredients and steps, allows definition
        SuggestionBoxCog - Takes feature suggestions and stores them. Probably simple, kept seperate for organization. 
    """

    print("H.E.L.P.eR. ready")


bot.run(token)
