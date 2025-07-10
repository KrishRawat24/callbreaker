# 🃏 Call Breaker Bot

An interactive Call Breaker multiplayer card game powered by `discord.py` and a live Flask dashboard — with private card DMs, spade logic, and real-time score tracking.

---

## 🚀 Features

- 🔄 **Full Turn Cycle**: Each player's turn is enforced with suit-following and spade rules
- 🧠 **Smart Rules**: 
  - Must play higher card of the same suit if available
  - If not, play a spade (if available)
  - If not, play any lower card
- 📩 **Private Cards**: Cards are distributed via Discord DMs to each player
- 🖥 **Live Dashboard**:
  - See last played card
  - See whose turn it is
  - Real-time scoreboard updates
- 🖱️ **Play with Buttons**: Discord buttons for easy card play (optional)

---


## 🔧 Setup

```bash
git clone https://github.com/KrishRawat24/callbreaker.git
cd callbreaker
pip install -r requirements.txt
