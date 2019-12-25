from discord.ext import commands
import time


class CogTest(commands.Cog):
    def __init__(self, bot):
        self.index = 0
        self.bot = bot
        self.channel = self.bot.get_channel(int(open("resources/Channel.txt", "r").readline()))
        bot.loop.create_task(self.tester())

    async def tester(self):
        await bot.wait_until_ready()
        print("Loop test good")
        self.channel = self.bot.get_channel(int(open("resources/Channel.txt", "r").readline()))
        while not bot.is_closed():
            await self.channel.send("Just wanted to point out the reference I made with the bot. ")
            time.sleep(1000)


bot = commands.Bot(command_prefix="!")
token = open("resources/APIKey.txt", "r").readline()
channel = int(open("resources/Channel.txt", "r").readline())

guild = bot.get_guild(int(guild))
channel = bot.get_channel(627329365520154646)
print(bot.guilds)
print(channel)
print(guild)


async def tester():
    while not bot.is_closed():
        await bot.wait_until_ready()
        channel = bot.get_channel(627329365520154646)
        print("Loop test good")
        await channel.send("test")
        time.sleep(10)


@bot.event
async def on_ready():
    print("Ready")


bot.add_cog(CogTest(bot))
# bot.loop.create_task(tester())

bot.run(token)
