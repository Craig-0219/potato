import asyncio
import os

import discord
from dotenv import load_dotenv

GUILD_ID = 1314820221957046282


async def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set in the environment.")

    intents = discord.Intents.none()
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        try:
            guild = client.get_guild(GUILD_ID)
            if guild is None:
                print(f"Guild {GUILD_ID} not found. The bot may not be in it.")
                return

            print(f"Leaving guild: {guild.name} ({guild.id})")
            await guild.leave()
            print("Left guild successfully.")
        finally:
            await client.close()

    try:
        await client.start(token)
    except Exception as exc:
        await client.close()
        raise SystemExit(f"Failed to run client: {exc}") from exc


if __name__ == "__main__":
    asyncio.run(main())
