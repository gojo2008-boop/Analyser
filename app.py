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
    """Parse KO events, tracking direct and passive kills separately."""
    if not replay_data or "log" not in replay_data:
        return {}

    battle_log = replay_data["log"].split("\n")
    players = replay_data.get("players", [])
    player1 = players[0] if len(players) > 0 else "Player 1"
    player2 = players[1] if len(players) > 1 else "Player 2"

    nickname_to_species = {}
    pokemon_to_player = {}
    all_pokemon = {player1: set(), player2: set()}
    kills = {player1: {}, player2: {}}
    deaths = {player1: {}, player2: {}}
    last_attacker = {}

    poke_pattern = r"\|poke\|(p\d)\|([^,]+),"
    switch_pattern = r"\|switch\|(p\d[a-z]?): ([^|]+)\|([^,|]+)"
    attack_pattern = r"\|move\|(p\d[a-z]?): ([^|]+)\|([^|]+)"
    faint_pattern = r"\|faint\|(p\d[a-z]?): ([^|]+)"
    passive_damage_pattern = r"\|damage\|(p\d[a-z]?): ([^|]+) was hurt by ([^|]+)"

    for line in battle_log:
        # Identify Pokémon and their owners
        poke_match = re.search(poke_pattern, line)
        if poke_match:
            player_slot, species = poke_match.groups()
            owner = player1 if player_slot == "p1" else player2
            nickname_to_species[species] = species
            pokemon_to_player[species] = owner
            all_pokemon[owner].add(species)

        switch_match = re.search(switch_pattern, line)
        if switch_match:
            player_slot, nickname, species = switch_match.groups()
            owner = player1 if player_slot.startswith("p1") else player2
            nickname_to_species[nickname] = species
            pokemon_to_player[nickname] = owner
            all_pokemon[owner].add(species)

        attack_match = re.search(attack_pattern, line)
        if attack_match:
            player_slot, attacker_nickname, move = attack_match.groups()
            attacker = nickname_to_species.get(attacker_nickname, attacker_nickname)
            attacker_owner = pokemon_to_player.get(attacker_nickname, "Unknown Player")
            last_attacker["last"] = (attacker, attacker_owner, "direct")

        faint_match = re.search(faint_pattern, line)
        if faint_match:
            player_slot, fainted_nickname = faint_match.groups()
            fainted_pokemon = nickname_to_species.get(fainted_nickname, fainted_nickname)
            fainted_owner = pokemon_to_player.get(fainted_nickname, "Unknown Player")

            # Track kills
            if "last" in last_attacker:
                attacker, attacker_owner, kill_type = last_attacker["last"]
                if attacker_owner in kills:
                    if attacker not in kills[attacker_owner]:
                        kills[attacker_owner][attacker] = {"direct": 0, "passive": 0}
                    kills[attacker_owner][attacker][kill_type] += 1

            # Track deaths
            if fainted_owner in deaths:
                if fainted_pokemon not in deaths[fainted_owner]:
                    deaths[fainted_owner][fainted_pokemon] = 0
                deaths[fainted_owner][fainted_pokemon] += 1

        # Track passive kills from hazards and indirect damage
        passive_damage_match = re.search(passive_damage_pattern, line)
        if passive_damage_match:
            player_slot, damaged_nickname, hazard_type = passive_damage_match.groups()
            damaged_pokemon = nickname_to_species.get(damaged_nickname, damaged_nickname)
            damaged_owner = pokemon_to_player.get(damaged_nickname, "Unknown Player")

            # If this Pokémon dies next, it counts as a passive kill for the last attacker
            last_attacker["last"] = (damaged_pokemon, damaged_owner, "passive")

    return player1, player2, kills, deaths, all_pokemon

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        replay_url = request.form["replay_url"]
        replay_data = fetch_replay_data(replay_url)

        if replay_data:
            player1, player2, kills, deaths, all_pokemon = parse_kills(replay_data)
            return render_template("result.html", player1=player1, player2=player2, kills=kills, deaths=deaths, all_pokemon=all_pokemon)
        else:
            return render_template("index.html", error="Failed to fetch replay data.")

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)

