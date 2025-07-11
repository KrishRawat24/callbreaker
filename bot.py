import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
from dotenv import load_dotenv
import random
import asyncio
from html2image import Html2Image
from typing import Any

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Flask app
app = Flask(__name__)
@app.route('/')
def index():
    return "Call Breaker Bot is running!"
def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Game state
players = []
player_hands = {}
player_bids = {}
player_tricks = {}
current_turn_index = 0
current_suit = None
current_round = []
all_throws = {}
game_in_progress = False
command_prefix_str = "!"

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=lambda bot, msg: command_prefix_str, intents=intents)

@bot.command()
async def setprefix(ctx: commands.Context, new_prefix: str):
    global command_prefix_str
    command_prefix_str = new_prefix
    await ctx.send(f"✅ Prefix changed to `{command_prefix_str}`")

@bot.command()
async def join(ctx: commands.Context):
    if game_in_progress:
        await ctx.send("🚫 A game is already in progress.")
        return
    if ctx.author not in players:
        players.append(ctx.author)
        await ctx.send(f"✅ {ctx.author.mention} joined the game!")

@bot.command()
async def start(ctx: commands.Context):
    global game_in_progress, current_turn_index, player_bids, player_tricks, player_hands, all_throws

    if len(players) < 2:
        await ctx.send("Need at least 2 players to start.")
        return
    game_in_progress = True
    deck = [f"{rank}{suit}" for rank in list("23456789TJQKA") for suit in ['♠', '♥', '♦', '♣']]
    random.shuffle(deck)

    cards_per_player = len(deck) // len(players)
    leftover = len(deck) % len(players)
    for i, player in enumerate(players):
        hand = deck[i * cards_per_player: (i + 1) * cards_per_player]
        player_hands[player] = hand
        player_tricks[player] = 0
        all_throws[player] = []

    if leftover:
        left_cards = deck[-leftover:]
        await ctx.send(f"🃏 Leftover cards: {', '.join(left_cards)}")

    await ctx.send("🎯 Game started! Everyone please enter your bid using `!bid <number>`")
    current_turn_index = random.randint(0, len(players) - 1)

@bot.command()
async def bid(ctx: commands.Context, number: int):
    if ctx.author not in players:
        await ctx.send("You're not in the game.")
        return
    if ctx.author in player_bids:
        await ctx.send("You've already placed a bid.")
        return
    player_bids[ctx.author] = number
    await ctx.send(f"{ctx.author.mention} placed a bid of {number}")

    if len(player_bids) == len(players):
        await ctx.send("🃏 All bids are in! Let's begin.")
        await bot.get_channel(ctx.channel.id).send(f"🎮 {players[current_turn_index].mention}, it's your turn to throw!")

@bot.command()
async def throw(ctx: commands.Context, card: str):
    global current_turn_index, current_suit

    if ctx.author != players[current_turn_index]:
        await ctx.send("🚫 It's not your turn.")
        return
    if card not in player_hands[ctx.author]:
        await ctx.send("🚫 You don't have that card.")
        return

    suit = card[-1]
    if not current_round:
        current_suit = suit
    else:
        same_suit = [c for c in player_hands[ctx.author] if c[-1] == current_suit]
        spades = [c for c in player_hands[ctx.author] if c[-1] == '♠']
        if suit != current_suit:
            if same_suit:
                await ctx.send("🚫 You must throw the same suit if you have one.")
                return
            elif suit != '♠' and spades:
                await ctx.send("🚫 You must throw a spade if you don’t have the suit.")
                return

    current_round.append((ctx.author, card))
    player_hands[ctx.author].remove(card)
    all_throws[ctx.author].append(card)

    if len(current_round) < len(players):
        current_turn_index = (current_turn_index + 1) % len(players)
        await ctx.send(f"✅ {ctx.author.mention} threw {card}. Next: {players[current_turn_index].mention}")
    else:
        suit_cards = [(p, c) for p, c in current_round if c[-1] == current_suit]
        if not suit_cards:
            suit_cards = [(p, c) for p, c in current_round if c[-1] == '♠']
        winner = max(suit_cards, key=lambda x: "23456789TJQKA".index(x[1][0]))
        player_tricks[winner[0]] += 1
        current_turn_index = players.index(winner[0])
        await ctx.send(f"🏆 {winner[0].mention} won the round with {winner[1]}!")

        current_round.clear()
        current_suit = None

        if all(len(h) == 0 for h in player_hands.values()):
            await end_game(ctx)
        else:
            await ctx.send(f"🎮 {players[current_turn_index].mention}, it's your turn to throw!")

    await render_game_image(ctx)

# --- Add a help command ---
@bot.command(name="helpme")
async def helpme(ctx: commands.Context):
    await ctx.send(f"""
🧠 **Call Breaker Bot Commands**:
`!setprefix <new_prefix>` – Change the command prefix
`!join` – Join the game
`!start` – Start the game and deal cards
`!bid <number>` – Place your bid for the round
`!throw <card>` – Play a card (e.g. `10♠`, `Q♥`)
""")

# --- Add error handlers ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❗ Missing argument: `{error.param.name}`. Use `!helpme` for usage.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❓ Unknown command. Use `!helpme` to see available commands.")
    else:
        await ctx.send(f"⚠️ An error occurred: {str(error)}")

async def end_game(ctx: commands.Context):
    global game_in_progress
    results = []
    for p in players:
        bid = player_bids.get(p, 0)
        tricks = player_tricks.get(p, 0)
        win = "✅" if bid == tricks else "❌"
        results.append(f"{p.name}: Bid {bid}, Got {tricks} → {win}")
    await ctx.send("🎲 Game Over!\n" + "\n".join(results))
    reset_game()

def reset_game():
    global players, player_hands, player_bids, player_tricks, current_turn_index, current_suit, current_round, game_in_progress, all_throws
    players.clear()
    player_hands.clear()
    player_bids.clear()
    player_tricks.clear()
    current_round.clear()
    all_throws.clear()
    current_suit = None
    current_turn_index = 0
    game_in_progress = False

async def render_game_image(ctx: commands.Context):
    hti = Html2Image()
    rows = ""
    for player in players:
        cards_html = ''.join(f'<span class="card">{c}</span>' for c in all_throws[player])
        rows += f'<div class="player"><strong>{player.name}</strong>: {cards_html}</div>'
    html = f""" <html>
<head>
  <style>
    body {{
      font-family: sans-serif;
      background: white;
      padding: 20px;
    }}
    .player {{
      margin-bottom: 10px;
      font-size: 18px;
    }}
    .card {{
      display: inline-block;
      margin-right: 8px;
      padding: 4px 6px;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 20px;
      background: #f9f9f9;
    }}
  </style>
</head>
<body>
  {rows}
</body>
</html> """
    with open("table.html", "w") as f:
        f.write(html)
    hti.screenshot(html_file="table.html", save_as="game_table.png", size=(800, 400))
    await ctx.send(file=discord.File("game_table.png"))

# Run Flask + Bot
Thread(target=run_flask).start()
bot.run(TOKEN)
