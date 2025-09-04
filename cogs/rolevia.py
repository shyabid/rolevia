from discord.ext import commands
import discord
from discord.ui import View, Button, Select, Modal, TextInput
import json
import aiohttp
from typing import Optional, Union
from database import db

class Rolevia(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        
    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent views for all existing quizzes
        # This ensures buttons work after bot restart
        pass

    @commands.command()
    async def sync(self, ctx):
        self.bot.tree.copy_global_to(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        
    @commands.hybrid_group(
        name='rolevia'
    )
    @commands.has_permissions(manage_roles=True)
    async def rolevia(self, ctx):
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="Rolevia Commands",
                description="Available commands:",
                color=discord.Color.purple()
            )
            embed.add_field(
                name="/rolevia setup", 
                value="Create a new quiz setup", 
                inline=False
            )
            embed.add_field(
                name="/rolevia logger <channel>", 
                value="Set the logging channel for quiz attempts", 
                inline=False
            )
            embed.add_field(
                name="/rolevia webhook <url>", 
                value="Set up a webhook for sending quiz embeds", 
                inline=False
            )
            embed.add_field(
                name="/rolevia send", 
                value="Send a quiz embed to a channel", 
                inline=False
            )
            await ctx.send(embed=embed)
    
    @rolevia.command(
        name="setup",
        description="Create a new Rolevia quiz setup."
    )
    @commands.has_permissions(manage_roles=True)
    async def setup(self, ctx: discord.ext.commands.Context):
        if ctx.interaction:
            await ctx.interaction.response.send_message(
                "Click the button below to create a new Rolevia quiz.",
                view=CreateRoleviaView()
            )
        else:
            await ctx.send(
                "Click the button below to create a new Rolevia quiz.",
                view=CreateRoleviaView()
            )

    @rolevia.command(
        name="logger",
        description="Set the logging channel for quiz attempts."
    )
    @commands.has_permissions(manage_roles=True)
    async def logger(self, ctx: discord.ext.commands.Context, channel: discord.TextChannel):
        db.set_log_channel(ctx.guild.id, channel.id)
        
        embed = discord.Embed(
            title="Logger Channel Set",
            description=f"Quiz attempts will now be logged to {channel.mention}",
            color=discord.Color.green()
        )
        
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

    @rolevia.command(
        name="webhook",
        description="Set up a webhook for sending quiz embeds."
    )
    @commands.has_permissions(manage_roles=True)
    async def webhook(self, ctx: discord.ext.commands.Context, webhook_url: str):
        # Validate webhook URL
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            embed = discord.Embed(
                title="Invalid Webhook URL",
                description="Please provide a valid Discord webhook URL.",
                color=discord.Color.red()
            )
            if ctx.interaction:
                await ctx.interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return
        
        db.set_webhook_url(ctx.guild.id, webhook_url)
        
        embed = discord.Embed(
            title="Webhook Set",
            description="Quiz embeds will now be sent via webhook with server avatar and name.",
            color=discord.Color.green()
        )
        
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx.send(embed=embed)

    @rolevia.command(
        name="send",
        description="Send a quiz embed to a channel."
    )
    @commands.has_permissions(manage_roles=True)
    async def send(self, ctx: discord.ext.commands.Context):
        modal = SendQuizModal()
        
        if ctx.interaction:
            await ctx.interaction.response.send_modal(modal)
        else:
            await ctx.send("This command can only be used as a slash command.")

class SendQuizModal(Modal):
    def __init__(self):
        super().__init__(title="Send Quiz Embed")
        
        self.quiz_id_input = TextInput(
            label="Quiz ID",
            placeholder="Enter the quiz ID to send",
            required=True
        )
        
        self.channel_input = TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID to send to",
            required=True
        )
        
        self.embed_json_input = TextInput(
            label="Custom Embed JSON (optional)",
            style=discord.TextStyle.paragraph,
            placeholder='{"title": "Custom Title", "description": "Custom Description", "color": 0x9932cc}',
            required=False,
            max_length=4000
        )
        
        self.title_input = TextInput(
            label="Simple Title (if not using JSON)",
            placeholder="Quiz Available!",
            required=False
        )
        
        self.description_input = TextInput(
            label="Simple Description (if not using JSON)",
            style=discord.TextStyle.paragraph,
            placeholder="Take this quiz to earn a role!",
            required=False
        )
        
        self.add_item(self.quiz_id_input)
        self.add_item(self.channel_input)
        self.add_item(self.embed_json_input)
        self.add_item(self.title_input)
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quiz_id = int(self.quiz_id_input.value)
            channel_id = int(self.channel_input.value)
            
            quiz_data = db.get_quiz(quiz_id)
            if not quiz_data:
                await interaction.response.send_message("Quiz not found!", ephemeral=True)
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("Channel not found!", ephemeral=True)
                return
            
            # Create embed
            embed = None
            if self.embed_json_input.value.strip():
                # Use JSON embed
                try:
                    embed_data = json.loads(self.embed_json_input.value)
                    embed = discord.Embed.from_dict(embed_data)
                except json.JSONDecodeError:
                    await interaction.response.send_message("Invalid JSON format!", ephemeral=True)
                    return
            else:
                # Use simple title/description
                role = interaction.guild.get_role(quiz_data['role_id'])
                title = self.title_input.value if self.title_input.value else "Quiz Available!"
                description = (
                    self.description_input.value if self.description_input.value 
                    else f"Take this quiz to earn the {role.mention} role!\nPassing score: {quiz_data['passing_percentage']}%"
                )
                
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color.purple()
                )
            
            # Send via webhook if configured, otherwise send normally
            webhook_url = db.get_webhook_url(interaction.guild.id)
            if webhook_url:
                await self.send_via_webhook(webhook_url, embed, quiz_data, interaction.guild, channel)
            else:
                await channel.send(
                    embed=embed,
                    view=QuizStartView(quiz_data)
                )
            
            await interaction.response.send_message(f"Quiz sent to {channel.mention}!", ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("Invalid ID format!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    async def send_via_webhook(self, webhook_url: str, embed: discord.Embed, quiz_data: dict, guild: discord.Guild, channel: discord.TextChannel):
        # Create webhook from URL if it doesn't exist, or use the channel's webhook
        try:
            webhook = discord.Webhook.from_url(webhook_url, session=aiohttp.ClientSession())
            await webhook.send(
                embed=embed,
                username=guild.name,
                avatar_url=str(guild.icon.url) if guild.icon else None,
                view=PersistentQuizStartView(quiz_data['id'])
            )
            await webhook.session.close()
        except Exception as e:
            # Fallback to regular channel send if webhook fails
            await channel.send(
                embed=embed,
                view=PersistentQuizStartView(quiz_data['id'])
            )
            raise Exception(f"Webhook failed: {str(e)}")

class CreateRoleviaView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Create a new Rolevia", style=discord.ButtonStyle.primary)
    async def create_rolevia(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            "Select the number of questions:",
            view=QuestionNumberSelect(),
            ephemeral=True
        )

class QuestionNumberSelect(View):
    def __init__(self):
        super().__init__()
        self.questions = []
        self.current_question = 0
        self.messages_to_delete = []  
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 21)]
        self.number_select = Select(
            placeholder="Choose number of questions",
            min_values=1,
            max_values=1,
            options=options,
            disabled=False  
        )
        self.number_select.callback = self.number_selected
        self.add_item(self.number_select)

    async def number_selected(self, interaction: discord.Interaction):
        self.total_questions = int(self.number_select.values[0])
        self.number_select.disabled = True
        await interaction.response.edit_message(
            content=f"Selected {self.total_questions} questions",
            view=self
        )
        message = await interaction.followup.send(
            f"Click below to set Question 1/{self.total_questions}",
            view=SetQuestionView(self),
            ephemeral=True
        )
        self.messages_to_delete.append(message)

class SetQuestionView(View):
    def __init__(self, number_select: QuestionNumberSelect):
        super().__init__()
        self.number_select = number_select

    @discord.ui.button(label="Set Question", style=discord.ButtonStyle.primary)
    async def set_question(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
            
        modal = QuestionModal(title=f"Question {self.number_select.current_question + 1}")
        modal.number_select = self.number_select
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        self.number_select.questions.append(modal.question_data)
        self.number_select.current_question += 1
        
        if self.number_select.current_question < self.number_select.total_questions:
            message = await interaction.followup.send(
                f"Click below to set Question {self.number_select.current_question + 1}/{self.number_select.total_questions}",
                view=SetQuestionView(self.number_select),
                ephemeral=True
            )
            self.number_select.messages_to_delete.append(message)
        else:
            for msg in self.number_select.messages_to_delete:
                try:
                    await msg.delete()
                except:
                    pass
            
            await interaction.followup.send(
                "Select the role to assign upon quiz completion:",
                view=RoleSelectView(self.number_select.questions, interaction),
                ephemeral=True
            )

class QuestionModal(Modal):
    def __init__(self, title):
        super().__init__(title=title)
        self.number_select = None
        self.question_input = TextInput(label="Question:")
        self.options_input = TextInput(
            label="Options (separated by |):", 
            max_length=4000,
            style=discord.TextStyle.paragraph,
            placeholder="Option 1|Option 2|Option 3|Option 4"
        )
        self.correct_answer_input = TextInput(
            label="Correct Answer(s) (numbers separated by |):",
            placeholder="1|2|3 or just 1"
        )
        self.imglink_input = TextInput(label="Image Link:", required=False)
        self.add_item(self.question_input)
        self.add_item(self.options_input)
        self.add_item(self.correct_answer_input)
        self.add_item(self.imglink_input)
        self.question_data = {}

    async def on_submit(self, interaction: discord.Interaction):
        correct_answers = [int(x.strip()) for x in self.correct_answer_input.value.split('|')]
        
        self.question_data = {
            "question": self.question_input.value,
            "options": self.options_input.value.split('|'),
            "correct_answers": correct_answers,
            "imglink": self.imglink_input.value
        }
        try:
            msg = await interaction.response.send_message(
                "Question saved!", 
                ephemeral=True
            )
            if hasattr(self, 'number_select') and self.number_select:
                msg = await interaction.original_response()
                self.number_select.messages_to_delete.append(msg)
        except:
            pass

class RoleSelectView(View):
    def __init__(self, questions, interaction: discord.Interaction):
        super().__init__()
        self.questions = questions
        self.guild = interaction.guild
        
        self.role_select = discord.ui.RoleSelect(
            placeholder="Choose a role",
            min_values=1,
            max_values=1,
            disabled=False 
        )
        self.role_select.callback = self.role_selected
        self.add_item(self.role_select)

    async def role_selected(self, interaction: discord.Interaction):
        role = self.role_select.values[0]   
        
        self.role_select.disabled = True
        await interaction.response.edit_message(
            content=f"Selected role: {role.name}",
            view=self
        )
        
        quiz_data = {
            "questions": self.questions,
            "role_id": role.id
        }
        
        await interaction.followup.send(
            "Select the passing percentage:",
            view=PassingPercentageView(quiz_data),
            ephemeral=True
        )

class PassingPercentageView(View):
    def __init__(self, quiz_data):
        super().__init__()
        self.quiz_data = quiz_data
        options = [discord.SelectOption(label=f"{i}%", value=str(i)) for i in range(0, 101, 10)]
        self.percent_select = Select(
            placeholder="Choose passing percentage",
            options=options,
            min_values=1,
            max_values=1
        )
        self.percent_select.callback = self.percentage_selected
        self.add_item(self.percent_select)

    async def percentage_selected(self, interaction: discord.Interaction):
        passing_percentage = int(self.percent_select.values[0])
        self.quiz_data["passing_percentage"] = passing_percentage
        
        # Save quiz to database
        quiz_id = db.save_quiz(
            interaction.guild.id,
            self.quiz_data["questions"],
            self.quiz_data["role_id"],
            passing_percentage
        )
        
        await interaction.response.edit_message(
            content=f"Quiz created successfully! Quiz ID: {quiz_id}\nUse `/rolevia send` to send this quiz to a channel.",
            view=None
        )

class QuizStartView(View):
    def __init__(self, quiz_data):
        super().__init__()
        self.quiz_data = quiz_data
        self.timeout = 98989898

    @discord.ui.button(label="Start Quiz", style=discord.ButtonStyle.success)
    async def start_quiz(self, interaction: discord.Interaction, button: Button):
        quiz_view = QuizView(self.quiz_data, interaction.user)
        await quiz_view.start_quiz(interaction)

class PersistentQuizStartView(View):
    def __init__(self, quiz_id: int = None):
        super().__init__(timeout=None)
        self.quiz_id = quiz_id
        custom_id = f"start_quiz_{quiz_id}" if quiz_id else "start_quiz"
        self.start_button = discord.ui.Button(
            label="Start Quiz", 
            style=discord.ButtonStyle.success, 
            custom_id=custom_id
        )
        self.start_button.callback = self.start_quiz_callback
        self.add_item(self.start_button)

    async def start_quiz_callback(self, interaction: discord.Interaction):
        # Extract quiz ID from custom_id
        custom_id = interaction.data['custom_id']
        if custom_id.startswith("start_quiz_"):
            quiz_id = int(custom_id.split("_")[-1])
            quiz_data = db.get_quiz(quiz_id)
            if quiz_data:
                quiz_view = QuizView(quiz_data, interaction.user)
                await quiz_view.start_quiz(interaction)
            else:
                await interaction.response.send_message("Quiz not found!", ephemeral=True)
        else:
            await interaction.response.send_message("Invalid quiz button!", ephemeral=True)

class QuizView:
    def __init__(self, quiz_data, user):
        self.quiz_data = quiz_data
        self.user = user
        self.current_question = 0
        self.correct_answers = 0
        self.total_questions = len(quiz_data["questions"])
        self.current_message = None

    async def start_quiz(self, interaction: discord.Interaction):
        question_data = self.quiz_data["questions"][self.current_question]
        embed = self.create_question_embed(question_data)
        view = QuestionView(question_data, self)
        message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        self.current_message = await interaction.original_response()

    def create_question_embed(self, question_data):
        options_text = "\n".join(f"{i}. {option.strip()}" for i, option in enumerate(question_data["options"], 1))
        
        embed = discord.Embed(
            description=f"**{question_data['question']}**\n\n{options_text}",
            color=discord.Color.purple()
        )
        
        embed.set_author(name=f"Question {self.current_question + 1}/{self.total_questions}")
        if question_data["imglink"]:
            embed.set_image(url=question_data["imglink"])
        return embed

class QuestionView(View):
    def __init__(self, question_data, quiz_view):
        super().__init__()
        self.question_data = question_data
        self.quiz_view = quiz_view
        
        for i, option in enumerate(question_data["options"], 1):
            self.add_item(QuestionButton(i, option.strip()))

class QuestionButton(Button):
    def __init__(self, number, option):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=str(number),
            custom_id=str(number)
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        quiz_view = self.view.quiz_view
        if int(self.custom_id) in self.view.question_data["correct_answers"]:
            quiz_view.correct_answers += 1

        quiz_view.current_question += 1
        
        if quiz_view.current_message:
            try:
                await quiz_view.current_message.delete()
            except:
                pass

        question_data = quiz_view.quiz_data["questions"][quiz_view.current_question] if quiz_view.current_question < quiz_view.total_questions else None
        
        if question_data:
            embed = quiz_view.create_question_embed(question_data)
            view = QuestionView(question_data, quiz_view)
            message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            quiz_view.current_message = message
        else:
            # Show results and log
            await self.finish_quiz(interaction, quiz_view)

    async def finish_quiz(self, interaction: discord.Interaction, quiz_view):
        passing_percentage = quiz_view.quiz_data.get("passing_percentage", 70)
        required_correct = (quiz_view.total_questions * passing_percentage) / 100
        passed = quiz_view.correct_answers >= required_correct
        
        # Log the attempt
        db.log_quiz_attempt(
            interaction.guild.id,
            interaction.user.id,
            quiz_view.quiz_data.get('id', 0),
            quiz_view.correct_answers,
            quiz_view.total_questions,
            passed
        )
        
        embed = discord.Embed(
            title="Quiz Results",
            description=f"Score: {quiz_view.correct_answers}/{quiz_view.total_questions} ({quiz_view.correct_answers / quiz_view.total_questions * 100:.2f}%)",
        )

        if passed:
            role = interaction.guild.get_role(quiz_view.quiz_data["role_id"])
            await interaction.user.add_roles(role)
            embed.add_field(
                name="Congratulations!", 
                value=f"You passed and received the {role.mention} role!"
            )
            embed.color = discord.Color.green()
        else:
            embed.add_field(
                name="Sorry!", 
                value="You did not pass the quiz. Try again!"
            )
            embed.color = discord.Color.red()
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Send log to logging channel if configured
        log_channel_id = db.get_log_channel(interaction.guild.id)
        if log_channel_id:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="Quiz Attempt Logged",
                    color=discord.Color.green() if passed else discord.Color.red()
                )
                log_embed.add_field(name="User", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Score", value=f"{quiz_view.correct_answers}/{quiz_view.total_questions}", inline=True)
                log_embed.add_field(name="Passed", value="✅ Yes" if passed else "❌ No", inline=True)
                log_embed.add_field(name="Quiz ID", value=quiz_view.quiz_data.get('id', 'Unknown'), inline=True)
                log_embed.timestamp = discord.utils.utcnow()
                
                try:
                    await log_channel.send(embed=log_embed)
                except:
                    pass

async def setup(bot):
    await bot.add_cog(Rolevia(bot))