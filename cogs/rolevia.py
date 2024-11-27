from discord.ext import commands
import discord
from discord.ui import View, Button, Select, Modal, TextInput

class Rolevia(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    @commands.command()
    async def sync(self, ctx):
        self.bot.tree.copy_global_to(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        
    @commands.hybrid_group(
        name='rolevia'
    )
    @commands.has_permissions(manage_roles=True)
    async def rolevia(self, ctx):
        pass
    
    @rolevia.command(
        name="create",
        description="Create a new Rolevia quiz."
    )
    @commands.has_permissions(manage_roles=True)
    async def create(
        self, 
        ctx: discord.ext.commands.Context
    ):
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

class CreateRoleviaView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Create a new Rolevia", style=discord.ButtonStyle.primary)
    async def create_rolevia(self, interaction: discord.Interaction, button: discord.ui.Button):
        # For non-ephemeral messages, we can edit
        if not interaction.response.is_done():
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
        # Disable the select after getting the value
        self.number_select.disabled = True
        # First respond to the interaction
        await interaction.response.edit_message(
            content=f"Selected {self.total_questions} questions",
            view=self
        )
        # Then send the next view
        message = await interaction.followup.send(
            f"Click below to set Question 1/{self.total_questions}",
            view=SetQuestionView(self),
            ephemeral=True
        )
        self.messages_to_delete.append(message)

    async def send_next_question(self, interaction: discord.Interaction):
        if self.current_question >= self.total_questions:
            # Clean up messages
            for message in self.messages_to_delete:
                try:
                    await message.delete()
                except:
                    pass

            await interaction.followup.send(
                "Select the role to assign upon quiz completion:",
                view=RoleSelectView(self.questions, interaction),
                ephemeral=True
            )
            return

        message = await interaction.followup.send(
            f"Click below to set Question {self.current_question + 1}/{self.total_questions}",
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
            pass  # Ignore edit errors for ephemeral messages
            
        modal = QuestionModal(title=f"Question {self.number_select.current_question + 1}")
        modal.number_select = self.number_select  # Pass number_select to modal
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
            self.number_select.messages_to_delete.append(message)  # Add this line
        else:
            # Clean up all setup messages
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
        self.number_select = None  # Will be set by SetQuestionView
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
        # Convert correct answers string to list of integers
        correct_answers = [int(x.strip()) for x in self.correct_answer_input.value.split('|')]
        
        self.question_data = {
            "question": self.question_input.value,
            "options": self.options_input.value.split('|'),
            "correct_answers": correct_answers,  # Changed from correct_answer to correct_answers
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
            pass  # Ignore any interaction errors

class RoleSelectView(View):
    def __init__(self, questions, interaction: discord.Interaction):
        super().__init__()
        self.questions = questions
        self.guild = interaction.guild
        options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in self.guild.roles 
            if not role.managed and role.name != "@everyone"
        ]
        self.role_select = Select(
            placeholder="Choose a role", 
            options=options,
            disabled=False  # Add this
        )
        self.role_select.callback = self.role_selected
        self.add_item(self.role_select)

    async def role_selected(self, interaction: discord.Interaction):
        role_id = int(self.role_select.values[0])
        role = interaction.guild.get_role(role_id)
        
        self.role_select.disabled = True
        await interaction.response.edit_message(
            content=f"Selected role: {role.name}",
            view=self
        )
        
        quiz_data = {
            "questions": self.questions,
            "role_id": role_id
        }
        
        await interaction.followup.send(
            "Select the passing percentage:",
            view=PassingPercentageView(quiz_data),
            ephemeral=True
        )

class QuizStartModal(Modal):
    def __init__(self):
        super().__init__(title="Quiz Start Message Settings")
        self.title_input = TextInput(
            label="Embed Title",
            placeholder="Quiz Available!",
            required=False
        )
        self.description_input = TextInput(
            label="Embed Description",
            style=discord.TextStyle.paragraph,
            placeholder="Take this quiz to earn the role!",
            required=False
        )
        self.add_item(self.title_input)
        self.add_item(self.description_input)

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
        
        # Show modal first
        modal = QuizStartModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        # After modal is submitted, update the original message
        try:
            await interaction.message.edit(
                content=f"Selected passing percentage: {passing_percentage}%",
                view=None  # Remove the view since we're done with it
            )
        except:
            pass  # Ignore any edit errors

        # Get role and create embed
        role = interaction.guild.get_role(self.quiz_data["role_id"])
        
        # Use custom title/description if provided, otherwise use defaults
        title = modal.title_input.value if modal.title_input.value else "Quiz Available!"
        description = (
            modal.description_input.value if modal.description_input.value 
            else f"Take this quiz to earn the {role.mention} role!\nPassing score: {passing_percentage}%"
        )
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.purple()
        )
        
        await interaction.channel.send(
            embed=embed,
            view=QuizStartView(self.quiz_data)
        )

class QuizStartView(View):
    def __init__(self, quiz_data):
        super().__init__()
        self.quiz_data = quiz_data
        self.timeout = 98989898  # Set a high timeout

    @discord.ui.button(label="Start Quiz", style=discord.ButtonStyle.success)
    async def start_quiz(self, interaction: discord.Interaction, button: Button):
        # Remove button disabling
        quiz_view = QuizView(self.quiz_data, interaction.user)
        await quiz_view.start_quiz(interaction)

class QuizView:
    def __init__(self, quiz_data, user):
        self.quiz_data = quiz_data
        self.user = user
        self.current_question = 0
        self.correct_answers = 0
        self.total_questions = len(quiz_data["questions"])
        self.message = None  # Add this to store the question message
        self.current_message = None  # Track current question message

    async def start_quiz(self, interaction: discord.Interaction):
        question_data = self.quiz_data["questions"][self.current_question]
        embed = self.create_question_embed(question_data)
        view = QuestionView(question_data, self)
        message = await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        self.current_message = await interaction.original_response()

    def create_question_embed(self, question_data):
        # Create numbered options list
        options_text = "\n".join(f"{i}. {option.strip()}" for i, option in enumerate(question_data["options"], 1))
        
        embed = discord.Embed(
            title=f"Question {self.current_question + 1}/{self.total_questions}",
            description=f"{question_data['question']}\n\n{options_text}",
            color=discord.Color.purple()
        )
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

    async def disable_all_buttons(self):
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

class QuestionButton(Button):
    def __init__(self, number, option):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=str(number),  # Just show the number
            custom_id=str(number)
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        quiz_view = self.view.quiz_view
        # Check if selected answer is in the list of correct answers
        if int(self.custom_id) in self.view.question_data["correct_answers"]:
            quiz_view.correct_answers += 1

        quiz_view.current_question += 1
        
        if quiz_view.current_message:
            try:
                await quiz_view.current_message.delete()
            except:
                pass

        # Handle next question or finish
        question_data = quiz_view.quiz_data["questions"][quiz_view.current_question] if quiz_view.current_question < quiz_view.total_questions else None
        
        if question_data:
            embed = quiz_view.create_question_embed(question_data)
            view = QuestionView(question_data, quiz_view)
            message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            quiz_view.current_message = message
        else:
            # Show results
            passing_percentage = quiz_view.quiz_data.get("passing_percentage", 70)  # Default to 70% if not set
            required_correct = (quiz_view.total_questions * passing_percentage) / 100
            passed = quiz_view.correct_answers >= required_correct
            
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

async def setup(bot):
    await bot.add_cog(Rolevia(bot))
