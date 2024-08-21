import os
import discord
import sqlite3
from discord.ext import commands
from datetime import datetime, timedelta
import random
import asyncio



# Set up bot token
TOKEN = ""

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Enable the members intent
bot = commands.Bot(command_prefix='', intents=intents)

# Initialize database connection
conn = sqlite3.connect('coins.db')
c = conn.cursor()

# Create table if not exists with correct schema
c.execute('''CREATE TABLE IF NOT EXISTS user_coins
             (user_id TEXT PRIMARY KEY, coins INTEGER, last_daily TIMESTAMP, last_weekly TIMESTAMP)''')

# Commit changes
conn.commit()

# Create table if not exists with correct schema
c.execute('''CREATE TABLE IF NOT EXISTS user_inventory
             (user_id TEXT, item TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (user_id, item))''')
conn.commit()

# Add the following SQL statement to add the count column if it does not exist
c.execute('''PRAGMA table_info(user_inventory)''')
columns = c.fetchall()
if not any(col[1] == 'count' for col in columns):
    c.execute('''ALTER TABLE user_inventory ADD COLUMN count INTEGER DEFAULT 1''')
    conn.commit()


# Function to get user's inventory from database
def get_user_inventory(user_id: str) -> dict:
    try:
        c.execute('SELECT item, count FROM user_inventory WHERE user_id=?', (user_id,))
        result = c.fetchall()
        print("User inventory from database:", result)  # Debug print
        inventory = {item: count for item, count in result}
        print("Constructed inventory dictionary:", inventory)  # Debug print
        return inventory
    except Exception as e:
        print(f"Error in get_user_inventory: {e}")
        return {}


# Function to get user's coins and last daily time from database
def get_user_data(user_id: str) -> (int, str, str):
    c.execute('SELECT coins, last_daily, last_weekly FROM user_coins WHERE user_id=?', (user_id,))
    result = c.fetchone()
    if result:
        coins, last_daily, last_weekly = result
    else:
        coins = 0
        last_daily = None
        last_weekly = None
    return coins, last_daily, last_weekly


# Function to update user's coins and last daily time in database
def update_user_data(user_id: str, coins: int, last_daily: str, last_weekly: str) -> None:
    c.execute('REPLACE INTO user_coins (user_id, coins, last_daily, last_weekly) VALUES (?, ?, ?, ?)',
              (user_id, coins, last_daily, last_weekly))
    conn.commit()


@bot.command()
async def transfer(ctx, recipient: discord.Member, amount: int):
    sender_id = str(ctx.author.id)
    recipient_id = str(recipient.id)

    print(f"Sender ID: {sender_id}")
    print(f"Recipient ID: {recipient_id}")

    # Check if sender has enough coins
    sender_coins, _, _ = get_user_data(sender_id)
    if sender_coins < amount:
        await ctx.send("You don't have enough coins to transfer.")
        return

    # Perform the transfer
    current_time = datetime.utcnow().isoformat()
    update_user_data(sender_id, sender_coins - amount, current_time, current_time)
    recipient_coins, _, _ = get_user_data(recipient_id)
    update_user_data(recipient_id, recipient_coins + amount, current_time, current_time)

    await ctx.send(f"{ctx.author.mention} has transferred {amount} coins to {recipient.mention}.")


# Function to handle the daily command
def handle_daily(user_id: str) -> str:
    coins, last_daily, _ = get_user_data(user_id)
    if last_daily is None or datetime.utcnow() - datetime.fromisoformat(last_daily) >= timedelta(days=1):
        coins_awarded = random.randint(200, 5000)
        update_user_data(user_id, coins + coins_awarded, datetime.utcnow().isoformat(), None)
        return f"You got your daily coins! You now have {coins + coins_awarded} coins."
    else:
        return "You have already claimed your daily coins today. Try again later."

# Function to handle the spawn_coins command
async def spawn_coins(channel, amount: int, recipient: discord.User):
    recipient_id = str(recipient.id)
    user_coins, _, _ = get_user_data(recipient_id)
    update_user_data(recipient_id, user_coins + amount, None, None)
    await channel.send(f"{recipient.mention} has been awarded {amount} coins.")


# Function to handle the weekly command
def handle_weekly(user_id: str) -> str:
    coins, _, last_weekly = get_user_data(user_id)
    if last_weekly is None or datetime.utcnow() - datetime.fromisoformat(last_weekly) >= timedelta(weeks=1):
        coins_awarded = random.randint(5000, 10000)
        update_user_data(user_id, coins + coins_awarded, None, datetime.utcnow().isoformat())
        return f"You got your weekly coins! You now have {coins + coins_awarded} coins."
    else:
        return "You have already claimed your weekly coins this week. Try again later."


# Function to handle betting command
def handle_bet(user_id: str, amount: int, choice: str) -> str:
    coins, _, _ = get_user_data(user_id)
    if coins < amount:
        return "Insufficient balance to place the bet."

    if choice.lower() not in ['heads', 'tails']:
        return "Invalid choice. Please choose 'heads' or 'tails'."

    result = random.choice(['heads', 'tails'])
    if result == choice.lower():
        update_user_data(user_id, coins + amount, None, None)
        return f"You won! You gained {amount} :coin:. Your new balance is {coins + amount} :coin:"
    else:
        update_user_data(user_id, coins - amount, None, None)
        return f"You lost! You lost {amount} :coin:. Your new balance is {coins - amount} :coin:"

# Function to wipe all users' coins (assuming you want to remove all coins)
def wipe_all_coins():
    try:
        c.execute('UPDATE user_coins SET coins=0')
        conn.commit()
        print("All users' coins have been wiped.")
    except Exception as e:
        print(f"Error wiping all coins: {e}")

# Function to add item to user's inventory
def add_item_to_inventory(user_id: str, item: str) -> None:
    try:
        # Check if the item is already in the user's inventory
        c.execute('SELECT count FROM user_inventory WHERE user_id=? AND item=?', (user_id, item))
        result = c.fetchone()
        if result:
            count = result[0] + 1
            print(f"Item '{item}' found in inventory. Current count: {result[0]}, Incrementing count to {count}.")
            c.execute('UPDATE user_inventory SET count=? WHERE user_id=? AND item=?', (count, user_id, item))
        else:
            # Item is not in the inventory, so insert it with count 1
            c.execute('INSERT INTO user_inventory (user_id, item, count) VALUES (?, ?, 1)', (user_id, item))
            print("Item added to inventory successfully.")
        conn.commit()

        # Debug: Retrieve and print the user's inventory after updating
        c.execute('SELECT item, count FROM user_inventory WHERE user_id=?', (user_id,))
        updated_inventory = c.fetchall()
        print("Updated user inventory:", updated_inventory)
    except Exception as e:
        print(f"Error in add_item_to_inventory: {e}")


@bot.command()
async def flip_coin(ctx):
    # Spinning coin animation using Unicode characters
    coin_animation = [
        "⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"
    ]

    # Send the spinning animation
    message = await ctx.send("Flipping the coin...")
    for i in range(10):
        await message.edit(content=coin_animation[i % len(coin_animation)])
        await asyncio.sleep(0.5)  # Adjust the delay as needed

    # Randomly choose between 'heads' and 'tails'
    result = random.choice(['heads', 'tails'])

    # Send the final result of the coin flip
    await message.edit(content=f"The coin landed on: {result}")


# Command to handle daily coins
@bot.command(name='eg_daily')  # Renaming the command
async def eg_daily(ctx):
    user_id = str(ctx.author.id)
    response = handle_daily(user_id)
    await ctx.send(response)


# Command to handle weekly coins
@bot.command(name='eg_weekly')
async def weekly(ctx):
    user_id = str(ctx.author.id)
    response = handle_weekly(user_id)
    await ctx.send(response)


# Command to handle betting
@bot.command()
async def bet(ctx, amount: int, choice: str):
    user_id = str(ctx.author.id)
    response = handle_bet(user_id, amount, choice)
    await ctx.send(response)


# Command to handle incoming messages
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    response = await get_response(bot, message)  # Pass the entire message object
    if response:
        await message.channel.send(response)
    else:
        print("Empty response received.")

emoji_to_index = {
    '1️⃣': 0,
    '2️⃣': 1,
    '3️⃣': 2,
    '4️⃣': 3,
    '5️⃣': 4,
    '6️⃣': 5,
    '7️⃣': 6,
    '8️⃣': 7,
    '9️⃣': 8,
}

# Function to handle incoming messages and commands
async def get_response(bot, message: discord.Message):
    user_id = str(message.author.id)
    lowered: str = message.content.lower()

    print("Received message:", lowered)  # Debug statement

    if lowered == '':
        return 'Well, you are awfully silent...'
    elif 'hello' in lowered:
        return 'Hello there!'
    elif 'how are you' in lowered:
        return 'Good, thank you!'
    elif lowered == '!wipe_all_coins' and user_id == '1156074251447701605':
        wipe_all_coins()
        return "All users' coins have been wiped."
    elif 'bye bye' in lowered:
        return 'Bye, see you next time'
    elif 'roll dice' in lowered:
        print("Roll dice command detected.")  # Debug statement
        parts = lowered.split(' ')
        if len(parts) == 3 and parts[0] == '!roll_dice':
            try:
                bet_amount = int(parts[1])
                user_choice = int(parts[2])
                rolled_number = random.randint(1, 6)
                if user_choice == rolled_number:
                    winnings = bet_amount * 5
                    return f'You rolled {rolled_number} and won {winnings} coins!'
                else:
                    return f'You rolled {rolled_number} and lost your bet of {bet_amount} coins.'
            except ValueError:
                return "Invalid bet amount or choice. Please use valid integers."
        else:
            return "Invalid roll dice command. Please use the format !roll_dice <bet_amount> <user_choice>."
    elif 'tell me about yourself' in lowered:
        return 'I am a bot that is programmed by MartoGG'
    elif 'eg help' in lowered:
        return 'Need help? Heres a list of avaiable commands coins: = check your coins balance, eg daily = claim your daily coins, eg weekly= claim your weekly coins, !bet <amount> <heads or tails> = bet your coins using this syntax, eg shop = get a list of shop items that are buyable with coins, eg inv = check your inventory of items, !spawn_coins @user <amount> = spawn coins (used by admins only and can be used instead of transfer command)'
    elif '1-50 random' in lowered:
        return f'Your number is... {random.randint(1, 50)}'
    elif '1-100 random' in lowered:
        return f'Your number is... {random.randint(1, 100)}'
    elif 'randomnum' in lowered:
        return f'Your number is...{random.randint(1, 100000000)}'
    elif 'random' in lowered:
        parts = lowered.split(' ')
        if len(parts) >= 2 and '-' in parts[0]:
            try:
                lower, upper = map(int, parts[0].split('-'))
                return f'Your number is... {random.randint(lower, upper)}'
            except ValueError:
                return 'Invalid range. Please use the format lower-upper random.'
        else:
            return 'Invalid command format. Please use the format lower-upper random.'
    elif lowered.startswith('coins') and len(lowered.split()) == 1:  # Check if the message is exactly 'coins'
        coins, _, _ = get_user_data(user_id)
        return f'You have {coins} :coin:'
    elif 'eg daily' in lowered:  # Check for the eg daily command
        return handle_daily(user_id)
    elif 'eg weekly' in lowered:
        return handle_weekly(user_id)
    elif lowered.startswith('eg cf'):  # Check for the eg cf command
        parts = lowered.split(' ')
        if len(parts) == 4 and parts[0] == 'eg' and parts[1] == 'cf':
            try:
                amount = int(parts[2])
                choice = parts[3]
                if choice.lower() not in ['heads', 'tails']:
                    return "Invalid choice. Please choose 'heads' or 'tails'."
                return handle_bet(user_id, amount, choice.lower())  # Ensure choice is lowercase
            except ValueError:
                return "Invalid bet amount. Please use a valid integer."
        else:
            return "Invalid bet command. Please use the format eg cf <amount> <choice>."

    elif lowered.startswith('!transfer'):  # Check for the transfer command
        parts = lowered.split(' ')
        if len(parts) == 3 and parts[0] == '!transfer':
            try:
                amount = int(parts[2])
                recipient = await commands.MemberConverter().convert(message, parts[1])
                return await transfer(bot, message, recipient, amount)
            except ValueError:
                return "Invalid transfer amount. Please use a valid integer."
            except commands.MemberNotFound:
                return "Recipient not found. Please provide a valid user mention."
        else:
            return "Invalid transfer command. Please use the format !transfer <@recipient> <amount>."
    elif lowered.startswith('eg say '):
        message = lowered.split('eg say ', 1)[1]
        return message
    elif lowered.startswith('!spawn_coins') and user_id in ['1156074251447701605', '886698297652314142', '912732640338145421', '1019153113279631421']:
        parts = lowered.split(' ')
        if len(parts) == 3 and parts[0] == '!spawn_coins':
            try:
                amount = int(parts[2])
                recipient_id = parts[1].strip('<@!>')
                print("Recipient ID:", recipient_id)  # Debug statement
                recipient = await bot.fetch_user(recipient_id)
                print("Recipient:", recipient)  # Debug statement
                return await spawn_coins(message.channel, amount=amount, recipient=recipient)
            except ValueError:
                return "Invalid coin amount. Please use a valid integer."
            except discord.NotFound:
                print("Recipient not found.")
                return "Recipient not found."
        else:
            return "Invalid command format. Please use the format !spawn_coins <@recipient> <amount>."
    elif 'eg shop' in lowered:
        # Define the items available in the shop and their prices
        shop_items = {
            '🚗 Car': 5000,
            '🏡 House': 1000,
            '🚁 Helicopter': 10000,
            '🎂 Cake': 2000,
            '🥥 Coconut': 3500,
            '🏝️ Island': 15000,
            '🍔 Burger': 150,
            '📱 Iphone': 25000,
            '🖥️ Imac': 100000
        }

        # Create an embedded message to display the shop items
        embed = discord.Embed(title="Shop Items", description="React with the corresponding emoji to buy the item",
                              color=0xFFD700)
        for i, (item, price) in enumerate(shop_items.items(), 1):
            # Check if the user already owns this item
            user_inventory = get_user_inventory(user_id)
            if item in user_inventory:
                item_name = f"{item} x{user_inventory[item]}"
            else:
                item_name = item
            embed.add_field(name=f"{i}. {item_name}", value=f"Price: {price} :coin:", inline=False)

        # Send the embedded message to the user
        shop_message = await message.channel.send(embed=embed)

        # Add reactions to the message for each item in the shop
        for i in range(1, len(shop_items) + 1):
            await shop_message.add_reaction(f"{i}\N{variation selector-16}\N{combining enclosing keycap}")

        # Define a check function for the reaction
        def reaction_check(reaction, user):
            print("Reaction emoji:", reaction.emoji)
            return user == message.author and reaction.message.id == shop_message.id and str(reaction.emoji).startswith(
                ('1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣',))

        # Wait for the user's reaction
        try:
            reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=reaction_check)
        except asyncio.TimeoutError:
            return "You took too long to respond."

        # Determine which item the user selected
        emoji_to_index = {'1️⃣': 0, '2️⃣': 1, '3️⃣': 2, '4️⃣': 3, '5️⃣': 4, '6️⃣': 5, '7️⃣': 6, '8️⃣': 7, '9️⃣': 8,}
        item_index = emoji_to_index[str(reaction.emoji)]
        selected_item = list(shop_items.keys())[item_index]
        item_price = list(shop_items.values())[item_index]

        # Check if the user has enough coins to buy the item
        user_coins, _, _ = get_user_data(user_id)
        if user_coins < item_price:
            return "Sorry, you don't have enough :coin: to purchase this item."

        # Deduct the price of the item from the user's coins and update the database
        update_user_data(user_id, user_coins - item_price, None, None)

        # Add purchased item to user's inventory
        add_item_to_inventory(user_id, selected_item)

        # Return the purchase confirmation message
        inventory = get_user_inventory(user_id)
        if inventory:
            inventory_text = '\n'.join([f"{item}: {count}" for item, count in inventory.items()])
            return f"{message.author.mention}, Your inventory:\n{inventory_text}"
        else:
            return f"{message.author.mention}, Your inventory is empty."
    elif 'eg inv' in lowered:
        try:
            print("eg inv command triggered.")  # Debug print
            user_id = str(message.author.id)
            inventory = get_user_inventory(user_id)
            if inventory:
                inventory_text = '\n'.join([f"{item}: {count}" for item, count in inventory.items()])
                return f"{message.author.mention}, Your inventory:\n{inventory_text}"
            else:
                return f"{message.author.mention}, Your inventory is empty."
        except Exception as e:
            print(f"Error in eg_inv command: {e}")
            return "An error occurred while fetching your inventory."



# Run the bot
bot.run(TOKEN)