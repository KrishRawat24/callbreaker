import discord
from discord.ext import commands
import json
import random
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

players = {}
game_state_file = "game_state.json"

SUITS = ['H', 'S', 'D', 'C']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def generate_deck():
    return [rank + suit for suit in SUITS for rank in RANKS]

def save_game_state(data):
    with open(game_state_file, 'w') as f:
        json.dump(data, f)

def load_game_state():
    if not os.path.exists(game_state_file):
        return {}
    with open(game_state_file, 'r') as f:
        return json.load(f)

@bot.command()
async def join(ctx):
    state = load_game_state()
    user = str(ctx.author)
    if "players" not in state:
        state["players"] = []
    if user not in state["players"]:
        state["players"].append(user)
        save_game_state(state)
        await ctx.send(f"{user} has joined the game.")
    else:
        await ctx.send("You're already in the game.")

@bot.command()
async def start(ctx):
    state = load_game_state()
    if "players" not in state or len(state["players"]) < 2:
        await ctx.send("Need at least 2 players to start.")
        return
    deck = generate_deck()
    random.shuffle(deck)
    hands = {player: [] for player in state["players"]}
    for i in range(len(deck)):
        hands[state["players"][i % len(state["players"])]] += [deck[i]]
    state["hands"] = hands
    state["turn"] = state["players"][0]
    state["last_card"] = None
    save_game_state(state)

    for player in hands:
        user = discord.utils.get(ctx.guild.members, name=player.split("#")[0])
        if user:
            await user.send(f"Your cards: {', '.join(hands[player])}")
    await ctx.send("Game started. Cards sent via DM.")

@bot.command()
async def play(ctx, card):
    state = load_game_state()
    user = str(ctx.author)
    if user != state.get("turn"):
        await ctx.send("It's not your turn!")
        return
    hand = state["hands"].get(user, [])
    if card not in hand:
        await ctx.send("You don't have that card.")
        return
    hand.remove(card)
    state["hands"][user] = hand
    state["last_card"] = card
    idx = state["players"].index(user)
    state["turn"] = state["players"][(idx + 1) % len(state["players"])]
    save_game_state(state)
    await ctx.send(f"{user} played {card}. It's now {state['turn']}'s turn.")

@bot.command()
async def score(ctx):
    state = load_game_state()
    scores = {p: 13 - len(state['hands'].get(p, [])) for p in state['players']}
    score_text = "\n".join([f"{p}: {s}" for p, s in scores.items()])
    await ctx.send(f"Scores:\n{score_text}")

@bot.command()
async def help(ctx):
    await ctx.send("""
**Call Breaker Commands**
!join - Join the game
!start - Start game and receive cards via DM
!play <card> - Play your card (e.g., !play 10H)
!score - Show current scores
!help - Show this message
""")
