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

bot = commands.Bot(command_prefix="!", intents=intents)

# File to persist game data between sessions
GAME_STATE_FILE = "game_state.json"

# Load or initialize game state
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

# Generate full deck
suits = ["♠", "♥", "♦", "♣"]
ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
deck = [f"{rank}{suit}" for suit in suits for rank in ranks]

# Score rank helper
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
        await ctx.send(f"{ctx.author.display_name}, you're not in the game.")
        return

    state["players"].remove(user_id)
    state["scores"].pop(user_id, None)
    state["hands"].pop(user_id, None)

    # If it was this player's turn, rotate turn
    if state["current_turn"] == user_id and state["players"]:
        current_idx = 0
        state["current_turn"] = state["players"][current_idx]

    save_state(state)

    await ctx.send(f"👋 {ctx.author.display_name} has left the game.")

    if not state["players"]:
        reset_state = {
            "players": [],
            "scores": {},
            "hands": {},
            "current_turn": "",
            "cards_played": [],
            "round": 1
        }
        save_state(reset_state)
        await ctx.send("Game has been reset since all players left.")

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
            hand = hands[pid]
            await user.send(f"🎴 Your cards: {', '.join(hand)}")
        except Exception as e:
            print(f"❌ Failed to DM player {pid}: {e}")
            await ctx.send(f"❌ Couldn't DM <@{pid}>. Make sure their DMs are enabled!")

    await ctx.send("🃏 Cards dealt! Check your DMs.\nFirst turn: <@{}>".format(players[0]))

@bot.command()
async def play(ctx, *, card_input):
    state = load_state()
    user_id = str(ctx.author.id)

    if user_id != state["current_turn"]:
        await ctx.send("❌ It's not your turn.")
        return

    hand = state["hands"].get(user_id, [])
    card_input = card_input.lower().strip()

    # --- Normalize text like "10 of hearts" to "10♥"
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

    # Parse input like "10 heart" or "king of spades"
    tokens = card_input.replace("of", "").split()
    if len(tokens) != 2:
        await ctx.send("❌ Invalid card format. Try `10 heart` or `king spade`.")
        return

    rank_raw, suit_raw = tokens
    rank = rank_map.get(rank_raw)
    suit = suit_map.get(suit_raw)

    if not rank or not suit:
        await ctx.send("❌ Invalid card. Example: `10 heart`, `king spade`, `A club`")
        return

    card = f"{rank}{suit}"

    if card not in hand:
        await ctx.send("❌ You don't have that card.")
        return

    # --- Enforce rules
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

    # --- Proceed with card play
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

@bot.command(name='rules')
async def rules(ctx):
    rules_text = """
🃏 **Call Breaker Game Rules**

1. **Objective**: Win the most rounds by playing the highest card.
2. **Turn Rules**:
   - You must play a higher card of the same suit if you have one.
   - If you don’t have a higher card of the same suit:
     - You **must** play a ♠️ Spade if you have it.
     - If you have no spade, play any lower card.
3. **Spades are trump**: Spades beat other suits.
4. **Cards are private**: Hands are sent via DM to each player.
5. **Gameplay**:
   - `!join` – Join the game
   - `!start` – Start the game
   - `!play <card>` – Play a card
   - `!score` – Show the scoreboard
   - `!reset` – Reset the match
   - `!leave` – Leave the match
   - `!rules` – Show rules again

🎯 Play smart, aim high, and use your spades wisely!
"""
    await ctx.send(rules_text)

@bot.command()
async def reset(ctx):
    state = {
        "players": [],
        "scores": {},
        "hands": {},
        "current_turn": "",
        "cards_played": [],
        "round": 1
    }
    save_state(state)
    await ctx.send("🔄 Game reset.")

@bot.command()
async def helpme(ctx):
    await ctx.send("""
🧠 **Call Breaker Bot Commands**:
`!join` – Join the game  
`!start` – Deal cards and begin  
`!play <card>` – Play your card (e.g. !play 10♥)  
`!score` – Show scoreboard  
`!reset` – Reset the game  
`!rules` – Game instructions  
`!leave` – Leave the game
Cards are shown privately in your DM. On your turn, play the highest card if possible.
""")

bot.run(TOKEN)
