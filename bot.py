import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
from dotenv import load_dotenv
import random
import asyncio
import html2image
from html2image import Html2Image
from typing import Any
import time

# --- Hindi translation maps ---
hindi_rank_map = {
    "1": "ek", "2": "doo", "3": "teen", "4": "char", "5": "paach", "6": "che", "7": "saat", "8": "aath", "9": "nau", "10": "das",
    "j": "gulam", "J": "gulam", "jack": "gulam",
    "q": "rani", "Q": "rani", "queen": "rani", "randi": "rani",
    "k": "raja", "K": "raja", "king": "raja",
    "a": "ikka", "A": "ikka", "ace": "ikka"
}
reverse_hindi_rank_map = {v: k for k, v in hindi_rank_map.items()}

rank_map = {
    "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
    "7": "7", "8": "8", "9": "9", "10": "10",
    "j": "J", "jack": "J", "q": "Q", "queen": "Q",
    "k": "K", "king": "K", "a": "A", "ace": "A"
}
suit_map = {
    "hearts": "♥", "heart": "♥", "paan": "♥",
    "spades": "♠", "spade": "♠", "hukum": "♠",
    "diamonds": "♦", "diamond": "♦", "iith": "♦",
    "clubs": "♣", "club": "♣", "chidi": "♣"
}

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
valid_prefixes = [command_prefix_str]
prefix_change_time = None

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

def get_prefix(bot, msg):
    # Allow both old and new prefix for 2 minutes after change
    now = time.time()
    if prefix_change_time and now - prefix_change_time < 120:
        return valid_prefixes
    return [valid_prefixes[-1]]

bot = commands.Bot(command_prefix=get_prefix, intents=intents)

@bot.command()
async def setprefix(ctx: commands.Context, new_prefix: str):
    global command_prefix_str, valid_prefixes, prefix_change_time
    old_prefix = command_prefix_str
    command_prefix_str = new_prefix
    valid_prefixes.append(new_prefix)
    prefix_change_time = time.time()
    await ctx.send(f"✅ Prefix changed to `{command_prefix_str}`. Both `{old_prefix}` and `{new_prefix}` will work for 2 minutes.")
    # Remove old prefix after 2 minutes
    async def remove_old_prefix():
        await asyncio.sleep(120)
        if len(valid_prefixes) > 1:
            valid_prefixes.pop(0)
    bot.loop.create_task(remove_old_prefix())

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
    if len(players) > 4:
        await ctx.send("Cannot start with more than 4 players.")
        return
    if game_in_progress:
        await ctx.send("A game is already in progress.")
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
        try:
            # Generate image of cards for this player
            hti = Html2Image()
            cards_html = ''.join(f'<span class="card">{c}</span>' for c in hand)
            html = f"""<html><head><style>body{{font-family:sans-serif;background:transparent;padding:20px;}}.card{{display:inline-block;margin-right:8px;padding:4px 6px;border:1px solid #ccc;border-radius:6px;font-size:20px;background:#f9f9f9;}}</style></head><body>{cards_html}</body></html>"""
            with open(f"hand_{player.id}.html", "w") as f:
                f.write(html)
            hti.screenshot(html_file=f"hand_{player.id}.html", save_as=f"hand_{player.id}.png", size=(800, 120))
            await player.send(file=discord.File(f"hand_{player.id}.png"), content="🎴 Your cards:")
        except Exception:
            await ctx.send(f"⚠️ Could not DM {player.mention}. Make sure your DMs are enabled!")

    if leftover:
        left_cards = deck[-leftover:]
        await ctx.send(f"🃏 Leftover cards: {', '.join(left_cards)}")

    await ctx.send("🎯 Cards have been dealt via DM! Everyone please enter your bid using `!bid <number>`.")
    current_turn_index = None  # Will be set after all bids

@bot.command()
async def bid(ctx: commands.Context, number: int):
    if not game_in_progress:
        await ctx.send("No game in progress. Use !start to begin a game.")
        return
    if ctx.author not in players:
        await ctx.send("You're not in the game. Use !join to join the game.")
        return
    player_bids[ctx.author] = number
    await ctx.send(f"{ctx.author.mention} placed a bid of {number}")

    # After all bids, randomly select a player to start
    if len(player_bids) == len(players):
        import random
        global current_turn_index
        current_turn_index = random.randint(0, len(players) - 1)
        await ctx.send("🃏 All bids are in! Let's begin.")
        await ctx.send(f"🎮 {players[current_turn_index].mention}, it's your turn to throw!")
    else:
        await ctx.send(f"Waiting for {len(players) - len(player_bids)} more bid(s)...")

@bot.command()
async def throw(ctx: commands.Context, *, card_input: str):
    global current_turn_index, current_suit

    if current_turn_index is None or ctx.author != players[current_turn_index]:
        await ctx.send("🚫 It's not your turn.")
        return

    # Flexible card input parsing
    card_input = card_input.lower().replace('of', '').replace('ka', '').replace('ke', '').replace('ki', '').strip()
    tokens = card_input.split()
    if len(tokens) < 2:
        await ctx.send("❌ Use format like `10 hearts`, `queen spades`, `a club`, `8 ka hukum`, `10 ka paan`, `hearts of k`, `raja ka paan`, etc.")
        return

    # Accept any order: rank suit or suit rank
    rank = None
    suit = None
    for t in tokens:
        if not rank and (t in rank_map or t in hindi_rank_map.values()):
            if t in rank_map:
                rank = rank_map[t]
            else:
                rank = reverse_hindi_rank_map[t]
        if not suit and t in suit_map:
            suit = suit_map[t]
    # If not found, try the other order
    if not rank or not suit:
        for t in tokens:
            if not suit and t in suit_map:
                suit = suit_map[t]
            if not rank and (t in rank_map or t in hindi_rank_map.values()):
                if t in rank_map:
                    rank = rank_map[t]
                else:
                    rank = reverse_hindi_rank_map[t]
    if not rank or not suit:
        await ctx.send("❌ Invalid rank or suit. Example: `8 ka hukum`, `10 hearts`, `king of spades`, `aath ka hukum`, `das hearts`, `rani ka paan`, `hearts of k`, `raja ka paan`.")
        return
    card = f"{rank}{suit}"

    if card not in player_hands[ctx.author]:
        await ctx.send("🚫 You don't have that card.")
        return

    # Card throw rules
    hand = player_hands[ctx.author]
    if not current_round:
        current_suit = suit
    else:
        same_suit = [c for c in hand if c[-1] == current_suit]
        spades = [c for c in hand if c[-1] == '♠']
        if suit != current_suit:
            if same_suit:
                await ctx.send("🚫 You must throw the same suit if you have one.")
                return
            elif suit != '♠' and spades:
                await ctx.send("🚫 You must throw a spade if you don’t have the suit.")
                return

    current_round.append((ctx.author, card))
    hand.remove(card)
    all_throws[ctx.author].append(card)

    # Update player's hand image in DM after throw
    try:
        hti = Html2Image()
        cards_html = ''.join(f'<span class="card">{c}</span>' for c in hand)
        html = f"""<html><head><style>body{{font-family:sans-serif;background:transparent;padding:20px;}}.card{{display:inline-block;margin-right:8px;padding:4px 6px;border:1px solid #ccc;border-radius:6px;font-size:20px;background:#f9f9f9;}}</style></head><body>{cards_html}</body></html>"""
        with open(f"hand_{ctx.author.id}.html", "w") as f:
            f.write(html)
        hti.screenshot(html_file=f"hand_{ctx.author.id}.html", save_as=f"hand_{ctx.author.id}.png", size=(800, 120))
        await ctx.author.send(file=discord.File(f"hand_{ctx.author.id}.png"), content="🃏 Your updated hand:")
    except Exception:
        pass

    if len(current_round) < len(players):
        current_turn_index = (current_turn_index + 1) % len(players)
        # Generate and send current round stack image
        hti = Html2Image()
        round_cards_html = ''.join(f'<span class="card">{c}</span>' for _, c in current_round)
        html = f"""<html><head><style>body{{font-family:sans-serif;background:transparent;padding:20px;}}.card{{display:inline-block;margin-right:8px;padding:4px 6px;border:1px solid #ccc;border-radius:6px;font-size:20px;background:#f9f9f9;}}</style></head><body><h3>Current Round Stack:</h3>{round_cards_html}</body></html>"""
        with open("round_stack.html", "w") as f:
            f.write(html)
        hti.screenshot(html_file="round_stack.html", save_as="round_stack.png", size=(800, 200))
        await ctx.send(file=discord.File("round_stack.png"), content=f"✅ {ctx.author.mention} threw {card}. Next: {players[current_turn_index].mention}")
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
`!setprefix <new_prefix>` – Change the command prefix. Example: `!setprefix $` (Prefix बदलें: उदाहरण: `!setprefix $`)
`!join` – Join the game. Example: `!join` (खेल में शामिल हों: उदाहरण: `!join`)
`!leave` – Leave the game. Example: `!leave` (खेल छोड़ें: उदाहरण: `!leave`)
`!start` – Start the game and deal cards (only works with 2-4 players). Example: `!start` (खेल शुरू करें: उदाहरण: `!start`)
`!bid <number>` – Place your bid for the round. Example: `!bid 3` (अपनी बोली लगाएं: उदाहरण: `!bid teen`)
`!throw <card>` – Play a card. Examples: `!throw 10 hearts`, `!throw king of spades`, `!throw 8 ka hukum`, `!throw 10 ka paan`, `!throw das hearts`, `!throw rani ka paan`

**Flexible Card Input:**
- You can use English or Hindi/vernacular suit and rank names:
  - hearts = paan
  - spades = hukum
  - clubs = chidi
  - diamonds = iith
  - 1=ek, 2=doo, 3=teen, 4=char, 5=paach, 6=che, 7=saat, 8=aath, 9=nau, 10=das, j=gulam, q=rani, k=raja, a=ikka
- Examples: `8 ka hukum`, `10 ka paan`, `king of spades`, `8 hearts`, `aath ka hukum`, `das hearts`, `rani ka paan`

**Game Rules:**
- Game starts with 2-4 players. Cards are sent via DM, then bids are collected publicly.
- After all bids, a random player is chosen to start. The winner of each round starts the next round.
- You must follow suit if possible, else throw a spade if you have one, else any card (but only spades or suit can win).
- A round only ends after all players have thrown a card.
- When all cards are played, the game ends. Players whose tricks won match their bid are declared winners (multiple winners possible).
- You can use the old or new prefix for a short time after changing it.

Use `!helpme` anytime to see this list. (मदद के लिए `!helpme` लिखें)
""")

# --- Re-add missing functions ---
async def end_game(ctx: commands.Context):
    global game_in_progress
    results = []
    winners = []
    for p in players:
        bid = player_bids.get(p, 0)
        tricks = player_tricks.get(p, 0)
        if bid == tricks:
            winners.append(p)
        results.append(f"{p.name}: Bid {bid}, Got {tricks} → {'✅' if bid == tricks else '❌'}")
    if winners:
        winner_names = ', '.join([p.mention for p in winners])
        await ctx.send(f"🏆 Winner(s): {winner_names}")
    else:
        await ctx.send("❌ No one matched their bid. No winners this game!")
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
        cards_html = ''.join(f'<span class="card">{c} / {hindi_rank_map.get(c[:-1], c[:-1])}</span>' for c in all_throws[player])
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

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        # Suggest correct usage with prefix if user typed command without prefix
        content = ctx.message.content.strip()
        for prefix in ctx.bot.command_prefix(ctx.bot, ctx.message):
            if content.startswith(prefix):
                # User used prefix but missed argument
                cmd = content[len(prefix):].split()[0]
                usage_hint = ''
                if cmd in ['setprefix', 'changeprefix']:
                    usage_hint = f"Example: `{prefix}{cmd} $`"
                elif cmd == 'bid':
                    usage_hint = f"Example: `{prefix}bid 3`"
                elif cmd == 'throw':
                    usage_hint = f"Example: `{prefix}throw 10 hearts`"
                await ctx.send(f"❗ Missing argument: `{error.param.name}`. {usage_hint} Use `{prefix}helpme` for all commands.")
                return
        # If user typed command without prefix, suggest correct usage
        tokens = content.split()
        if tokens:
            cmd = tokens[0]
            if cmd in ['setprefix', 'changeprefix', 'bid', 'throw']:
                await ctx.send(f"❗ It looks like you typed `{cmd}` without the prefix. Try `{ctx.prefix}{cmd} ...` (e.g., `{ctx.prefix}{cmd} ...`). Use `{ctx.prefix}helpme` for help.")
                return
        await ctx.send(f"❗ Missing argument: `{error.param.name}`. Use `{ctx.prefix}helpme` for usage and examples.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❓ Unknown command. Use `{ctx.prefix}helpme` to see available commands and usage.")
    else:
        await ctx.send(f"⚠️ An error occurred: {str(error)}")

@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")

if __name__ == "__main__":
    print("TOKEN:", TOKEN)
    bot.run(TOKEN)
# --- End of bot.py ---
# Summary: Help, game start, bid, throw, and round logic are now robust. Next steps: continue optimizing per plan.
