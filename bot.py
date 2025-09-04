from discord.ext import commands
import discord
import config
from database import db

class Bot(commands.Bot):
    def __init__(self, intents: discord.Intents, **kwargs):
        super().__init__(command_prefix=commands.when_mentioned_or('$'), intents=intents, **kwargs)

    async def setup_hook(self):
        for cog in config.cogs:
            try:
                await self.load_extension(cog)
            except Exception as exc:
                print(f'Could not load extension {cog} due to {exc.__class__.__name__}: {exc}')

    async def on_ready(self):
        print(f'Logged on as {self.user} (ID: {self.user.id})')
        
    async def on_interaction(self, interaction: discord.Interaction):
        # Handle persistent view interactions for quiz buttons
        if interaction.type == discord.InteractionType.component:
            if interaction.data.get('custom_id', '').startswith('start_quiz_'):
                # Import here to avoid circular imports
                from cogs.rolevia import QuizView
                
                custom_id = interaction.data['custom_id']
                quiz_id = int(custom_id.split('_')[-1])
                quiz_data = db.get_quiz(quiz_id)
                
                if quiz_data:
                    quiz_view = QuizView(quiz_data, interaction.user)
                    await quiz_view.start_quiz(interaction)
                else:
                    await interaction.response.send_message("Quiz not found!", ephemeral=True)
                return
        
        # Let other interactions be handled normally
        await self.process_application_commands(interaction)


intents = discord.Intents.default()
intents.message_content = True
bot = Bot(intents=intents)

bot.run(config.token)
