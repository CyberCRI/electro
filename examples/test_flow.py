"""Test Flow example."""

import uvicorn

from electro.app import app
from electro import Flow, MessageFlowStep
from electro.extra.i18n_gettext import templated_gettext as _

from electro.toolkit.discord_tweeks import enable_message_separator

from electro.triggers import CommandTrigger

from electro.flow_manager import global_flow_manager


class TestFlow(Flow):
    """Test Flow."""

    _triggers = [
        CommandTrigger("test_flow"),
    ]

    send_test_message = MessageFlowStep(
        _("test_flow_message"),
    )


global_flow_manager.add_flow(TestFlow())

# region Setting up the bot
# TODO: [2024-07-20 by Mykola] Move to a separate file
enable_message_separator()
#
#
# @bot.event
# async def on_connect():
#     """Start the services when the bot is ready."""
#     logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
#
#     logger.info(f"Starting the Tortoise ORM...")
#     await init_orm()
#
#     # Save the bot to the database
#     if not (bot_user := await User.get_or_none(id=bot.user.id)):
#         bot_user = await User.create(
#             id=bot.user.id,
#             username=bot.user.name,
#             discriminator=bot.user.discriminator,
#             is_bot=True,
#         )
#
#         logger.info(f"Saved the bot to the database: {bot_user=}")
#     else:
#         logger.debug(f"The bot is already in the database: {bot_user=}")
#
#
# @bot.listen("on_member_join")
# async def on_member_join(member: discord.Member):
#     await flow_manager.on_member_join(member)
#
#
# @bot.listen("on_member_update")
# async def on_member_update(before: discord.Member, after: discord.Member):
#     await flow_manager.on_member_update(before, after)
#
#
# @bot.listen("on_interaction")
# async def on_interaction(interaction: discord.Interaction):
#     await flow_manager.on_interaction(interaction)
#
#
# @bot.event
# async def on_message(message: discord.Message):
#     """Handle messages."""
#     return await flow_manager.on_message(message)
#
#
# # On bot joining a Guild (server), add that Guild to the database
# @bot.event
# async def on_guild_available(guild: discord.Guild):
#     """Handle the bot joining a Guild (server)."""
#     # Save the Guild to the database
#     guild_, is_created = await Guild.get_or_create(
#         id=guild.id,
#         defaults=dict(
#             name=guild.name,
#             icon=guild.icon.url if guild.icon else None,
#             banner=guild.banner.url if guild.banner else None,
#             description=guild.description,
#             preferred_locale=guild.preferred_locale,
#             afk_channel_id=guild.afk_channel.id if guild.afk_channel else None,
#             afk_timeout=guild.afk_timeout,
#             owner_id=guild.owner.id,
#         ),
#     )
#
#     if is_created:
#         logger.info(f"Created a new Guild: {guild_=}")
#     else:
#         logger.info(f"Found an existing Guild: {guild_=}")
#
#
# # Display a warning message on message edit
# @bot.event
# async def on_message_edit(before: discord.Message, after: discord.Message):
#     """Handle message edits."""
#     if before.author == bot.user:
#         return
#
#     if before.content != after.content:
#         await after.channel.send(
#             _("message_edit_warning").safe_substitute(
#                 user_mention=before.author.mention,
#             ),
#             delete_after=5,
#         )


if __name__ == "__main__":
    uvicorn.run(app=app, loop="asyncio")

# endregion
