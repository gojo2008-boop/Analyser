from flask import Flask, request, render_template
import requests
import re

app = Flask(__name__)

def fetch_replay_data(replay_url):
    """Fetch replay log data from a Pokémon Showdown replay link."""
    replay_id = replay_url.split("/")[-1]
    api_url = f"https://replay.pokemonshowdown.com/{replay_id}.json"

    response = requests.get(api_url)
    if response.status_code != 200:
        return None
    return response.json()

def parse_kills(replay_data):
    """Parse KO events with correct player and team tracking."""
    if not replay_data or "log" not in replay_data:
        return {}

    battle_log = replay_data["log"].split("\n")
    players = replay_data.get("players", [])
    player1 = players[0] if len(players) > 0 else "Player 1"
    player2 = players[1] if len(players) > 1 else "Player 2"

    nickname_to_species = {}
    pokemon_to_player = {}
    kills = {player1: {}, player2: {}}
    last_attacker = {}

    poke_pattern = r"\|poke\|(p\d)\|([^,]+),"
    switch_pattern = r"\|switch\|(p\d[a-z]?): ([^|]+)\|([^,|]+)"
    attack_pattern = r"\|move\|(p\d[a-z]?): ([^|]+)\|([^|]+)"
    faint_pattern = r"\|faint\|(p\d[a-z]?): ([^|]+)"

    for line in battle_log:
        poke_match = re.search(poke_pattern, line)
        if poke_match:
            player_slot, species = poke_match.groups()
            owner = player1 if player_slot == "p1" else player2
            nickname_to_species[species] = species
            pokemon_to_player[species] = owner

        switch_match = re.search(switch_pattern, line)
        if switch_match:
            player_slot, nickname, species = switch_match.groups()
            owner = player1 if player_slot.startswith("p1") else player2
            nickname_to_species[nickname] = species
            pokemon_to_player[nickname] = owner

        attack_match = re.search(attack_pattern, line)
        if attack_match:
            player_slot, attacker_nickname, move = attack_match.groups()
            attacker = nickname_to_species.get(attacker_nickname, attacker_nickname)
            attacker_owner = pokemon_to_player.get(attacker_nickname, "Unknown Player")
            last_attacker["last"] = (attacker, attacker_owner)

        faint_match = re.search(faint_pattern, line)
        if faint_match:
            player_slot, fainted_nickname = faint_match.groups()
            fainted_pokemon = nickname_to_species.get(fainted_nickname, fainted_nickname)
            fainted_owner = pokemon_to_player.get(fainted_nickname, "Unknown Player")

            if "last" in last_attacker:
                attacker, attacker_owner = last_attacker["last"]
                if attacker_owner in kills:
                    if attacker not in kills[attacker_owner]:
                        kills[attacker_owner][attacker] = []
                    kills[attacker_owner][attacker].append(fainted_pokemon)

    return player1, player2, kills

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        replay_url = request.form["replay_url"]
        replay_data = fetch_replay_data(replay_url)

        if replay_data:
            player1, player2, kills = parse_kills(replay_data)
            return render_template("result.html", player1=player1, player2=player2, kills=kills)
        else:
            return render_template("index.html", error="Failed to fetch replay data.")

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)

