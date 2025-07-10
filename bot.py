import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import random
import json

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ---- Dynamic Prefix ----
PREFIX_FILE = "prefix.json"

def load_prefix():
    if os.path.exists(PREFIX_FILE):
        with open(PREFIX_FILE, "r") as f:
            return json.load(f).get("prefix", "!")
    return "!"

def save_prefix(new_prefix):
    with open(PREFIX_FILE, "w") as f:
        json.dump({"prefix": new_prefix}, f)

bot = commands.Bot(command_prefix=lambda bot, msg: load_prefix(), intents=intents)

# ---- Game State File ----
GAME_STATE_FILE = "game_state.json"

def load_state():
    if os.path.exists(GAME_STATE_FILE):
        with open(GAME_STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "players": [],
        "scores": {},
        "hands": {},
        "current_turn": "",
        "cards_played": [],
        "round": 1
    }

def save_state(state):
    with open(GAME_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

suits = ["♠", "♥", "♦", "♣"]
ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
deck = [f"{rank}{suit}" for suit in suits for rank in ranks]

def card_value(card):
    rank = card[:-1]
    order = {str(n): n for n in range(2, 11)}
    order.update({"J": 11, "Q": 12, "K": 13, "A": 14})
    return order.get(rank, 0)

@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")
    await bot.tree.sync()

@bot.command()
async def changeprefix(ctx, new_prefix):
    save_prefix(new_prefix)
    await ctx.send(f"✅ Command prefix changed to `{new_prefix}`. Use `{new_prefix}helpme` from now.")

@bot.command()
async def join(ctx):
    state = load_state()
    user_id = str(ctx.author.id)
    if user_id not in state["players"]:
        state["players"].append(user_id)
        state["scores"][user_id] = 0
        save_state(state)
        await ctx.send(f"{ctx.author.display_name} joined the game!")
    else:
        await ctx.send("You're already in the game.")

@bot.command()
async def leave(ctx):
    state = load_state()
    user_id = str(ctx.author.id)

    if user_id not in state["players"]:
        await ctx.send("You're not in the game.")
        return

    state["players"].remove(user_id)
    state["scores"].pop(user_id, None)
    state["hands"].pop(user_id, None)

    if state["current_turn"] == user_id and state["players"]:
        state["current_turn"] = state["players"][0]

    save_state(state)
    await ctx.send(f"{ctx.author.display_name} left the game.")

@bot.command()
async def start(ctx):
    state = load_state()
    players = state["players"]
    if len(players) < 2:
        await ctx.send("Need at least 2 players to start.")
        return

    cards = deck.copy()
    random.shuffle(cards)

    hand_size = len(cards) // len(players)
    hands = {pid: cards[i * hand_size:(i + 1) * hand_size] for i, pid in enumerate(players)}
    state["hands"] = hands
    state["current_turn"] = players[0]
    state["cards_played"] = []
    save_state(state)

    for pid in players:
        try:
            user = await bot.fetch_user(int(pid))
            await user.send(f"🎴 Your cards: {', '.join(hands[pid])}")
        except Exception as e:
            await ctx.send(f"⚠️ Failed to DM <@{pid}>. Make sure their DMs are enabled!")

    await ctx.send(f"🃏 Cards dealt! First turn: <@{players[0]}>")

@bot.command()
async def play(ctx, *, card_input):
    state = load_state()
    user_id = str(ctx.author.id)

    if user_id != state["current_turn"]:
        await ctx.send("❌ It's not your turn.")
        return

    hand = state["hands"].get(user_id, [])
    card_input = card_input.lower().strip()

    rank_map = {
        "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
        "7": "7", "8": "8", "9": "9", "10": "10",
        "j": "J", "jack": "J", "q": "Q", "queen": "Q",
        "k": "K", "king": "K", "a": "A", "ace": "A"
    }
    suit_map = {
        "hearts": "♥", "heart": "♥",
        "spades": "♠", "spade": "♠",
        "diamonds": "♦", "diamond": "♦",
        "clubs": "♣", "club": "♣"
    }

    tokens = card_input.replace("of", "").split()
    if len(tokens) != 2:
        await ctx.send("❌ Use format like `10 hearts`, `queen spades`, or `a club`.")
        return

    rank = rank_map.get(tokens[0])
    suit = suit_map.get(tokens[1])

    if not rank or not suit:
        await ctx.send("❌ Invalid rank or suit.")
        return

    card = f"{rank}{suit}"

    if card not in hand:
        await ctx.send("❌ You don't have that card.")
        return

    if state["cards_played"]:
        lead_suit = state["cards_played"][0]["card"][-1]
        lead_value = card_value(state["cards_played"][0]["card"])
        same_suit_higher = [c for c in hand if c[-1] == lead_suit and card_value(c) > lead_value]

        if same_suit_higher and card not in same_suit_higher:
            await ctx.send("⚠️ You must play a higher card of the same suit.")
            return
        elif not same_suit_higher:
            spades = [c for c in hand if "♠" in c]
            if spades and "♠" not in card:
                await ctx.send("⚠️ You must throw a spade if you have no higher card.")
                return

    hand.remove(card)
    state["hands"][user_id] = hand
    state["cards_played"].append({"player": user_id, "card": card})
    save_state(state)

    await ctx.send(f"🃏 {ctx.author.display_name} played: {card}")

    players = state["players"]
    idx = players.index(user_id)
    next_idx = (idx + 1) % len(players)
    state["current_turn"] = players[next_idx]
    save_state(state)

    await ctx.send(f"🔔 Next turn: <@{players[next_idx]}>")

@bot.command()
async def score(ctx):
    state = load_state()
    lines = ["📊 **Scores:**"]
    for pid, score in state["scores"].items():
        user = await bot.fetch_user(int(pid))
        lines.append(f"{user.display_name}: {score}")
    await ctx.send("\n".join(lines))

@bot.command()
async def rules(ctx):
    await ctx.send(f"""
🃏 **Call Breaker Game Rules**
1. Win rounds by playing the highest card.
2. Must play higher card of same suit if possible.
3. If not, throw a ♠️ if you have one.
4. If not, play any lower card.
5. Spades beat all other suits.
6. Use `join`, `start`, `play <card>`, `score`, `reset`, `leave`, `rules`, `changeprefix <symbol>`.
""")

@bot.command()
async def reset(ctx):
    save_state({
        "players": [],
        "scores": {},
        "hands": {},
        "current_turn": "",
        "cards_played": [],
        "round": 1
    })
    await ctx.send("🔄 Game reset.")

@bot.command()
async def helpme(ctx):
    prefix = load_prefix()
    await ctx.send(f"""
🧠 **Call Breaker Bot Commands**:
`{prefix}join` – Join the game  
`{prefix}start` – Start game and deal cards  
`{prefix}play <card>` – Play your card (e.g. `10 heart`, `ace spade`)  
`{prefix}score` – Show scoreboard  
`{prefix}reset` – Reset the game  
`{prefix}rules` – Game rules  
`{prefix}leave` – Leave the match  
`{prefix}changeprefix <new>` – Change bot prefix
""")

bot.run(TOKEN)
