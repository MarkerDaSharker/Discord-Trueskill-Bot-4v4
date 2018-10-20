# -*- coding: utf-8 -*-
"""
Created on Sun Aug 13 21:36:48 2017

@author: Marker + Dayne
"""

import discord
from discord.ext.commands import bot
from discord.ext import commands
import time
import random
from multiprocessing import Process
import asyncio
import sqlite3
import numpy as np
import itertools
import pandas as pd
import trueskill
import scipy.special

main_elo = trueskill.TrueSkill(mu = 4000, draw_probability = 0, backend = "mpmath", sigma=400, tau=4, beta=200)
main_elo.make_as_global()
GAME = False
RUNNING = False
db_path = "" #set to path of database
PLAYERS = []
results = dict()

ID = 0

LEAGUE = {}

cilent = discord.Client()
bot_prefix = "-"
client = commands.Bot(command_prefix=bot_prefix)
ban_list = [
    discord.Object("") # Savage
];

general_chat = discord.Object("") # set to copy id of general chat
bot_spam = discord.Object("") #set to copy id of a bot spam channel
lobby_channel = discord.Object("") #set to copy id of lobby channel

admin_channel = discord.Object("") #set to copy id of an admin channel
moderator_channel = discord.Object("") #set to copy id of a mod channel
mod_discussion_channel = discord.Object("") #set to copy id of a mod channel
warns_channel = discord.Object("") #set to copy id of a warns feed channel

# Set these to ids of various roles
admin_role = discord.Object("")
moderator_role = discord.Object("")
tribune_role = discord.Object("")
player_role = discord.Object("")
warning1_role = discord.Object("")
warning2_role = discord.Object("")
warning3_role = discord.Object("")
warning4_role = discord.Object("")
warning5_role = discord.Object("")
banned_role = discord.Object("")
optoutspam_role = discord.Object("")

replace_these_roles = [warning1_role.id, warning2_role.id, warning3_role.id, warning4_role.id, warning5_role.id, banned_role.id, player_role.id]
warning_roles = [warning1_role, warning2_role, warning3_role, warning4_role, warning5_role]

async def update_player_roles_util(user, warnings):
    roles = user.roles.copy()
    for i in range(len(roles) - 1, -1, -1):
        if roles[i].id in replace_these_roles:
            roles.remove(roles[i])
    
    # Add warning roles
    if warnings > 0:
        warn_index = max(0, min(4, (warnings - 1)))
        roles.append(warning_roles[warn_index])
        
        # Check ban status and update roles accordingly
        if warnings >= 5:
            roles.append(banned_role)
        else:
            roles.append(player_role)
    else:
        # Safe to give the player the player role back
        roles.append(player_role)
        
    await client.replace_roles(user, *roles)

def find_user_by_name(ctx, name):
    conn = sqlite3.connect(db_path, uri=True)
    c = conn.cursor()
    out = None
    
    if len(name) == 0:
        # Tried without an input
        out = ctx.message.author
    else:
        # Test to see if it's a ping
        server = ctx.message.server
        if name[0:2] == "<@":
            if name[2] == "!":
                player = server.get_member(name[3:-1])
            else:
                player = server.get_member(name[2:-1])
            if player is not None:
                out = player
        else:
            # Test to see if it's a username
            player = server.get_member_named(name)
            if player is not None:
                out = player
            else:
                # Check the database to see if it's a username
                conn = sqlite3.connect(db_path, uri=True)

                c = conn.cursor()
                c.execute("SELECT ID FROM players WHERE name LIKE ?", [name])
                result = c.fetchone()
                if result is not None:
                    player = server.get_member(result[0])
                    if player is not None:
                        out = player
                else:
                    # Check the database to see if it's LIKE a username
                    wildcard_name = name + "%"
                    c.execute("SELECT ID FROM players WHERE name LIKE ?", [wildcard_name])
                    result = c.fetchone()
                    if result is not None:
                        player = server.get_member(result[0])
                        if player is not None:
                            out = player
    conn.commit()
    conn.close()
    return out
    
def find_userid_by_name(ctx, name):
    conn = sqlite3.connect(db_path, uri=True)
    c = conn.cursor()
    out = None
    
    if len(name) == 0:
        # Tried without an input
        out = ctx.message.author.id
    else:
        # Test to see if it's a ping
        server = ctx.message.server
        if name[0:2] == "<@":
            if name[2] == "!":
                player = server.get_member(name[3:-1])
            else:
                player = server.get_member(name[2:-1])
            if player is not None:
                out = player.id
        else:
            # Test to see if it's a username
            player = server.get_member_named(name)
            if player is not None:
                out = player.id
            else:
                # Check the database to see if it's a username
                c.execute("SELECT ID FROM players WHERE name LIKE ?", [name])
                result = c.fetchone()
                if result is not None:
                    out = result[0]
                else:
                    # Check the database to see if it's LIKE a username
                    wildcard_name = name + "%"
                    c.execute("SELECT ID FROM players WHERE name LIKE ?", [wildcard_name])
                    result = c.fetchone()
                    if result is not None:
                        out = result[0]
    conn.commit()
    conn.close()
    return out

@client.event
async def on_member_join(member):
    conn = sqlite3.connect(db_path)

    for user in ban_list:
        if member.id:
            discord.Client.ban(member)
    
    c = conn.cursor()
    c.execute("SELECT name, warnings, fresh_warns FROM players WHERE ID = ?", [member.id])
    player = c.fetchone()
    if player is not None:
        name = player[0]
        warns = player[1] + player[2]
        await client.change_nickname(member, name)
        await update_player_roles_util(member, warns)

@client.command(pass_context=True)
async def register(ctx):
    conn = sqlite3.connect(db_path)

    c = conn.cursor()
    
    A = str(ctx.message.author.id)
    B = str(ctx.message.author.name)
    c.execute("SELECT elo FROM players WHERE ID = ?", [A])
    mon = c.fetchone()
    if mon == None:
        c.execute('INSERT INTO players VALUES(?, ?, 0, 0, 1000, NULL, 0, 0, 0, 0)', [A,B])
        await client.say("You are now registered!")
        await client.add_roles(ctx.message.author, player_role)
        #await client.change_nickname(ctx.message.author, B + " [1000]")
    else:
        await client.say("You have already registered!")
    
    conn.commit()
    conn.close()

@client.command(pass_context=True)
async def lobby(ctx):
    global PLAYERS, GAME
    conn = sqlite3.connect(db_path, uri=True)

    c = conn.cursor()
    
    if ctx.message.channel.id == lobby_channel.id:
        if GAME:
            PLAYERS = list(set(PLAYERS))
            NAMES = []
            for t in PLAYERS:
                c.execute("SELECT name, elo FROM players WHERE ID = ?", [t])
                result = c.fetchone()
                name = result[0]
                pts = result[1]
                NAMES.append(name + " [" + str(pts) + "]")
            
            if len(set(PLAYERS)) > 0:
                lobbystr = "Current Lobby **(" + str(len(set(PLAYERS))) + ")**: "
                for t in NAMES:
                    lobbystr += t + "   "
                    
                await client.say(lobbystr)
            elif ctx.message.channel.id == lobby_channel.id:
                await client.say("No lobby!")
        else:
            await client.say("No game! Please say *\"-start\"*")
            
    conn.close()
    
@client.command(pass_context=True, aliases=["j"])
async def join(ctx):
    global PLAYERS
    t = ctx.message.author.id

    conn = sqlite3.connect(db_path, uri=True)

    c = conn.cursor()
    
    c.execute("SELECT currentg FROM players WHERE ID = ?", [t])
    
    A = c.fetchone()[0] is None
    if ctx.message.channel.id == lobby_channel.id:
        if GAME and A:
            PLAYERS.append(ctx.message.author.id)
            c.execute("SELECT name, elo FROM players where ID = ?", [t])
            result = c.fetchone()
            name = result[0]
            pts = result[1]
            await client.send_message(bot_spam, content = "**" + name + " [" + str(pts) + "]** has joined the lobby! **(" + str(len(set(PLAYERS))) + ")**")
            await client.send_message(lobby_channel, content = "**" + name + " [" + str(pts) + "]** has joined the lobby! **(" + str(len(set(PLAYERS))) + ")**")
        elif GAME:
            await client.say("You are still in a game! Please report score with *\"-r \'Team 1 Score\' \'Team 2 Score\'\"*.")
        else:
            await client.say("No lobbies currently active! Please say *\"-start\"*.")
        
    conn.close()
    
@client.command(pass_context=True, aliases=["l"])
async def leave(ctx):
    global PLAYERS
    t = ctx.message.author.id

    conn = sqlite3.connect(db_path, uri=True)

    c = conn.cursor()
    
    if ctx.message.channel.id == lobby_channel.id:
        if GAME:
            try:
                PLAYERS = list(set(PLAYERS))
                PLAYERS.remove(ctx.message.author.id)
                c.execute("SELECT name, elo FROM players where ID = ?", [t])
                result = c.fetchone()
                name = result[0]
                pts = result[1]
                await client.send_message(bot_spam, content = "**" + name + " [" + str(pts) + "]** has removed their signup! **(" + str(len(set(PLAYERS))) + ")**")
                await client.send_message(lobby_channel, content = "**" + name + " [" + str(pts) + "]** has removed their signup! **(" + str(len(set(PLAYERS))) + ")**")
            except:
                True
        else:
            await client.say("No lobbies currently active! Please say *\"-start\"*.")
    
    conn.commit()
    conn.close()


@client.command(pass_context=True)
async def start(ctx):
    global GAME, RUNNING, PLAYERS
    if ctx.message.channel.id == lobby_channel.id:
        if(not RUNNING):
            PLAYERS = []
            await client.send_message(bot_spam, content = "New game hosted!")
            await client.send_message(lobby_channel, content = "@here\nNew game hosted!")
    
            counter = 0
            RUNNING = True
            GAME = True
            while (len(set(PLAYERS)) < 8 and counter < 90):
                await asyncio.sleep(30)
                counter += 1
                
            await client.send_message(bot_spam, content = "Game starting in 15 seconds...")
            await client.send_message(lobby_channel, content = "Game starting in 15 seconds...")
            await asyncio.sleep(10)
            GAME = False
            await asyncio.sleep(5)
            if(len(set(PLAYERS)) > 7):
                PLAYERS = list(set(PLAYERS))
                conn = sqlite3.connect(db_path)
    
                c = conn.cursor()
                
                np.random.shuffle(PLAYERS)
                
                ELOS = []
                values = []
                for t in PLAYERS:
                    c.execute("SELECT elo FROM players WHERE ID = ?", [t])
                    elo = c.fetchone()[0]
                    ELOS.append((t, int(elo)))
                    values.append(int(elo))
                    
                mu = np.mean(values)
                sigma = 300
                mask = np.ones(len(PLAYERS)).astype(bool)
                
                counterb = 0
                
                while(sum(mask) != 8) and counterb < 250000:
                    for k,x in enumerate(values):
                        mask[k] = np.random.uniform(0.0,1.0) < 1.0/2.0*(1.0+scipy.special.erf((x-mu)/(sigma*np.sqrt(2))))
                    counterb += 1
                
                if sum(mask) == 8:
                    ELOS = list(np.array(ELOS)[mask])
                    
                    team1 = sum([int(b[1]) for b in ELOS[0:4]])
                    team2 = sum([int(b[1]) for b in ELOS[4:8]])
                    
                    diff = abs(team1-team2)
                    
                    for t in itertools.permutations(ELOS, 8):
                        team1 = sum([int(b[1]) for b in t[0:4]])
                        team2 = sum([int(b[1]) for b in t[4:8]])
                        if abs(team1 - team2) < diff:
                            ELOS  = t
                            diff = abs(team1-team2)
                    c.execute("SELECT MAX(ID) from games")
                    gameID = c.fetchone()[0]
                    if gameID is None:
                        gameID = 1
                    else:
                        gameID = int(gameID) + 1
                    
                    
                    playerID = []
                    for t in ELOS:
                        playerID.append(t[0])
                        
                    
        
        
                    c.execute('INSERT INTO games VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL,NULL)', [gameID] + playerID)
                    
                    for t in playerID:
                        c.execute("UPDATE players SET currentg = ? WHERE ID = ?", [gameID, t])
                        
                    capt = 0
                    captid = ""
                    finalstr = "**Team 1 (" +str(sum([int(b[1]) for b in ELOS[0:4]])) + "):** "
                    for k,t in enumerate(playerID):
                        c.execute("SELECT name FROM players WHERE ID = ?", [t])
                        name = c.fetchone()[0]
                        if(capt < int(ELOS[k][1])):
                            capt = int(ELOS[k][1])
                            captid = name
                        finalstr += name + "   "
                        if k == 3:
                            finalstr += "**Captain: " + captid + "**\n**Team 2 (" + str(sum([int(b[1])for b in ELOS[4:8]])) +"):** "
                            capt = 0
                            captid = ""
                    
                    finalstr += "**Captain: " + captid + "**\nTotal ELO Difference: " + str(diff) + "."
                    
                    await client.send_message(bot_spam, content = finalstr)
                    await client.send_message(lobby_channel, content = finalstr)
                    
                    notestr = ""
                    for t in playerID:
                        notestr += "<@" + t + "> "

                    await client.send_message(lobby_channel, content = notestr)
                    
                    conn.commit()
        
                    conn.close()
                    PLAYERS = []
                else:
                    await client.send_message(bot_spam, content = "Could not balance lobby.")
                    await client.send_message(lobby_channel, content = "Could not balance lobby.")
                    PLAYERS = []
            else:
                await client.send_message(bot_spam, content = "Not Enough Players")
                await client.send_message(lobby_channel, content = "Not Enough Players")
                PLAYERS = []
                
            PLAYERS = []
            RUNNING = False
        else:
            await client.say("Game already started.")

@client.command(pass_context=True, aliases=["r", "s", "gg"])
async def score(ctx):
    
    message = ctx.message.content.split()
    try:
        valid = ctx.message.channel.id == lobby_channel.id and type(int(message[1])) == int and type(int(message[2])) == int
        if valid:
            conn = sqlite3.connect(db_path)

            c = conn.cursor()
            
            auth = ctx.message.author.id
            
            c.execute("SELECT currentg FROM players where ID = ?", [auth])
            
            currentg = c.fetchone()[0]
            if not currentg == None:
                try:
                    results[currentg][str(ctx.message.author.id)] = (int(message[1]),int(message[2]))
                except:
                    results[currentg] = dict()
                    results[currentg][str(ctx.message.author.id)] = (int(message[1]),int(message[2]))
                    
                                
                try:
                    draw = False
                    t1g = True
                    score = pd.Series(list(results[currentg].values())).value_counts()[pd.Series(list(results[currentg].values())).value_counts() > 5].keys()[0]
                    if score[0] == score[1]:
                        draw = True
                    if score[0] < score[1]:
                        t1g = False
                        
                    c.execute("SELECT * FROM games where ID = ?", [currentg])
                    ids = c.fetchone()[1:9]
                    
                    ELOS = []
                    for t in ids:
                        c.execute("SELECT elo FROM players where ID = ?", [t])
                        ELOS.append(c.fetchone()[0])
                        
                    team1 = sum(ELOS[0:4])
                    team2 = sum(ELOS[4:8])
                    
                    if t1g and not draw:
                        skill = trueskill.rate_1vs1(trueskill.Rating(team1),trueskill.Rating(team2))
                        team1n = skill[0].mu
                        team2n = skill[1].mu
                        
                    elif not draw:
                        skill = trueskill.rate_1vs1(trueskill.Rating(team2),trueskill.Rating(team1))
                        team2n = skill[0].mu
                        team1n = skill[1].mu
                        
                    else:
                        team1n = team1
                        team2n = team2
                        
                    team1diff = np.ceil((team1n - team1)/4.0)
                    team2diff = np.ceil((team2n - team2)/4.0)
                    
                    ELOS[0:4] = list(np.add(ELOS[0:4],team1diff))
                    ELOS[4:8] = list(np.add(ELOS[4:8],team2diff))
                    
                    
                    for k,t in enumerate(ids):
                        
                        c.execute("UPDATE players SET currentg = NULL where ID = ?", [t])
                        
                        if not draw:
                            c.execute("UPDATE players SET elo = ? where ID = ?", [int(ELOS[k]), t])
                            
                            c.execute("SELECT name FROM players where ID = ?", [t])
                            namen = c.fetchone()[0]
                            
                            #UserO = discord.Object(str(t))
                            #await client.change_nickname(UserO, namen + " ["+ str(ELOS[k]) + "]")
                            
                            if t1g and k < 4:
                                c.execute("UPDATE players SET win = win + 1 where ID = ?", [t])
                            elif k >= 4 and not t1g:
                                c.execute("UPDATE players SET win = win + 1 where ID = ?", [t])
                            else:
                                c.execute("UPDATE players SET loss = loss + 1 where ID = ?", [t])
                                
                    c.execute("UPDATE games SET s1 = ? where ID = ?", [score[0],currentg])
                    c.execute("UPDATE games SET s2 = ? where ID = ?", [score[1],currentg])
                    
                    del results[currentg]
                        
                    await client.send_message(bot_spam, content = "Game " + str(currentg) + " finished " + str(score[0]) + " - " + str(score[1]) + " with an ELO difference of +/- "
                                              + str(abs(team1diff)) + ".")
                    
                    await client.send_message(lobby_channel, content = "Game " + str(currentg) + " finished " + str(score[0]) + " - " + str(score[1]) + " with an ELO difference of +/- "
                                              + str(abs(team1diff)) + ".")
                    
                
                
                except:
                    1 == 1
                    True
            
            conn.commit()

            conn.close()
        
    except:
        True

@client.command(pass_context=True, aliases=["g", "getgames"])
async def games(ctx):
    global PLAYERS, GAME
    conn = sqlite3.connect(db_path, uri=True)

    c = conn.cursor()
    
    c.execute("SELECT ID FROM games WHERE s1 IS NULL")
    games = c.fetchall()
    
    if len(games) == 0:
        await client.say("No active games!")
    else:
        if len(games) == 1:
            await client.say("Found " + str(len(games)) + " active game!")
        else:
            await client.say("Found " + str(len(games)) + " active games!")
        count = 1
        for game in games:
            c.execute("SELECT p1, p2, p3, p4, p5, p6, p7, p8 FROM games WHERE ID is ?", game)
            players = c.fetchone()
            
            gameStr = "**Game " + str(count) + ": **\n**Team 1:** "
            count += 1
            playerCnt = 0
            for player in players:
                c.execute("SELECT name, elo FROM players where ID = ?", [player])
                result = c.fetchone()
                name = result[0]
                pts = result[1]
                gameStr += name + " [" + str(pts) + "]  "
                if playerCnt == 3:
                    gameStr += "\n**Team 2:** "
                playerCnt += 1

            await client.say(gameStr)
    
    
    conn.commit()
    conn.close()


@client.command(pass_context=True)
async def stats(ctx):
    global PLAYERS
    
    name = str(ctx.message.content)[7:]
    t = find_userid_by_name(ctx, name)
    if t is None:
        await client.say("No user found by that name!")
        return

    conn = sqlite3.connect(db_path, uri=True)

    c = conn.cursor()
    c.execute("SELECT name, elo, win, loss FROM players where ID = ?", [t])
    player = c.fetchone()
    
    if player is not None:
        name = player[0]
        pts = player[1]
        win = player[2]
        loss = player[3]
        total_games = win + loss
        if total_games == 0:
            await client.say("**" + name + "** played no games and has an elo of **" + str(pts) + "**!")
        else:
            winrate = float("{0:.2f}".format((win / total_games) * 100))
            await client.say("**" + name + "** has played **" + str(total_games) + "** games with a win rate of **" + str(winrate) + "%** (**" + str(win) + "**W - **" + str(loss) + "**L). Their elo: **" + str(pts) + "**.")
    else:
        await client.say("No user found by that name!")

    conn.commit()
    conn.close()
    
@client.command(pass_context=True)
async def compare(ctx, p1, p2):
    global PLAYERS

    conn = sqlite3.connect(db_path, uri=True)
    c = conn.cursor()
    
    t1 = find_userid_by_name(ctx, p1)
    if t1 is None:
        await client.say("No user found by the name \"" + p1 + "\"!")
        conn.commit()
        conn.close()
        return
    
    c.execute("SELECT name, elo FROM players where ID = ?", [t1])
    result = c.fetchone()
    if result is None:
        await client.say("No user found by the name \"" + p1 + "\"!")
        conn.commit()
        conn.close()
        return
    name1 = result[0]
    elo1 = str(result[1])
    

    t2 = find_userid_by_name(ctx, p2)
    if t2 is None:
        await client.say("No user found by the name \"" + p2 + "\"!")
        conn.commit()
        conn.close()
        return
    
    c.execute("SELECT name, elo FROM players where ID = ?", [t2])
    result = c.fetchone()
    if result is None:
        await client.say("No user found by the name \"" + p2 + "\"!")
        conn.commit()
        conn.close()
        return
    name2 = result[0]
    elo2 = str(result[1])
    
    wins_together = 0
    loss_together = 0
    wins_against  = 0
    loss_against  = 0
    
    c.execute("SELECT s1, s2, ID FROM games where (p1 == ? OR p2 == ? OR p3 == ? OR p4 == ?) AND (p1 == ? OR p2 == ? OR p3 == ? OR p4 == ?) AND s1 != s2", [t1, t1, t1, t1, t2, t2, t2, t2])
    game = c.fetchone()
    while game is not None:
        s1 = game[0]
        s2 = game[1]
        if s1 > s2:
            wins_together += 1
        elif s1 < s2:
            loss_together += 1
        
        game = c.fetchone()
    
    c.execute("SELECT s1, s2, ID FROM games where (p5 == ? OR p6 == ? OR p7 == ? OR p8 == ?) AND (p5 == ? OR p6 == ? OR p7 == ? OR p8 == ?) AND s1 != s2", [t1, t1, t1, t1, t2, t2, t2, t2])
    game = c.fetchone()
    while game is not None:
        s1 = game[0]
        s2 = game[1]
        
        if s1 < s2:
            wins_together += 1
        elif s1 > s2:
            loss_together += 1
        
        game = c.fetchone()

    c.execute("SELECT s1, s2 FROM games where (p1 == ? OR p2 == ? OR p3 == ? OR p4 == ?) AND (p5 == ? OR p6 == ? OR p7 == ? OR p8 == ?) AND s1 != s2", [t1, t1, t1, t1, t2, t2, t2, t2])
    game = c.fetchone()
    while game is not None:
        s1 = game[0]
        s2 = game[1]
        
        if s1 > s2:
            wins_against += 1
        elif s1 < s2:
            loss_against += 1
        
        game = c.fetchone()
    
    c.execute("SELECT s1, s2 FROM games where (p5 == ? OR p6 == ? OR p7 == ? OR p8 == ?) AND (p1 == ? OR p2 == ? OR p3 == ? OR p4 == ?) AND s1 != s2", [t1, t1, t1, t1, t2, t2, t2, t2])
    game = c.fetchone()
    while game is not None:
        s1 = game[0]
        s2 = game[1]
        
        if s1 < s2:
            wins_against += 1
        elif s1 > s2:
            loss_against += 1
        
        game = c.fetchone()

    total_together = wins_together + loss_together
    if total_together > 0:
        winrate_together = float("{0:.2f}".format((wins_together / total_together) * 100))
        str_together = "**" + name1 + " [" + elo1 + "]** and **" + name2 + " [" + elo2 + "]** have played **" + str(total_together) + "** games together with a win rate of **" + str(winrate_together) + "%** (**" + str(wins_together) + "**W - **" + str(loss_together) + "**L)."
    else:
        str_together = "**" + name1 + " [" + elo1 + "]** and **" + name2 + " [" + elo2 + "]** have not played together."
    
    total_against = wins_against + loss_against
    if total_against > 0:
        winrate_against = float("{0:.2f}".format((wins_against / total_against) * 100))
        str_against = "**" + name1 + " [" + elo1 + "]** has played against **" + name2 + " [" + elo2 + "]** a total of **" + str(total_against) + "** times with a win rate of **" + str(winrate_against) + "%** (**" + str(wins_against) + "**W - **" + str(loss_against) + "**L) ."
    else:
        str_against = "**" + name1 + " [" + elo1 + "]** and **" + name2 + " [" + elo2 + "]** have not played against each other."
    
    
    await client.say(str_together + "\n" + str_against)
    conn.commit()
    conn.close()

@client.command(pass_context=True, aliases=["name"])
async def rename(ctx):
    conn = sqlite3.connect(db_path)

    c = conn.cursor()
    
    A = str(ctx.message.author.id)
    B = str(ctx.message.author.name)
    c.execute("SELECT perms FROM players WHERE ID = ? AND perms & 1 = 0", [A])
    privs = c.fetchone()
    if privs is not None:
        space = str(ctx.message.content).find(" ")
        newName = str(ctx.message.content)[space + 1:]

        if len(str(ctx.message.content)) < (33-7):
            c.execute("UPDATE players SET name = ? where ID = ?", [newName, A])
            #c.execute("SELECT elo FROM players where ID = ?", [A])
            #elon = c.fetchone()[0]
            
            await client.change_nickname(ctx.message.author, newName)
            # await client.change_nickname(ctx.message.author, newName + " ["+ str(elon) + "]")
        else:
            await client.say("Invalid Length.")
    else:        
        await client.say("Insufficient permissions to use this command.")

    conn.commit()
    conn.close()
    

@client.command(pass_context=True, aliases=["cw", "checkwarn"])
async def checkwarns(ctx):
    conn = sqlite3.connect(db_path, uri=True)
    
    space = str(ctx.message.content).find(" ")
    if space == -1:
        name = ""
    else:
        name = str(ctx.message.content)[space + 1:]
    t = find_userid_by_name(ctx, name)
    if t is None:
        await client.say("No user found by that name!")
        conn.commit()
        conn.close()
        return

    c = conn.cursor()
    c.execute("SELECT name, warnings, fresh_warns FROM players where ID = ?", [t])
    player = c.fetchone()
    
    if player is not None:
        name = player[0]
        warns = player[1] + player[2]
        
        if warns is None:
            warns = 0
        
        out = "**" + name + "** has **" + str(warns) + "** warnings"
        
        # Check ban status
        if warns >= 5:
            out += " and is currently **banned**"
        
        await client.say(out + ".")
        #await update_player_roles_util(user, warns)
    else:
        await client.say("No user found by that name!")

    conn.commit()
    conn.close()

   
"""
Moderator commands
"""

@client.command(pass_context=True, hidden=True)
async def warn(ctx, name, warnings, reason, aliases=["w", "aw", "warns", "addwarn", "addwarns"]):
    is_mod_channel = ctx.message.channel.id == admin_channel.id \
                  or ctx.message.channel.id == moderator_channel.id \
                  or ctx.message.channel.id == mod_discussion_channel.id

    if is_mod_channel:
        t = find_userid_by_name(ctx, name)
        if t is None:
            await client.say("No user found by that name!")
            return
        
        user = find_user_by_name(ctx, name)

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name, warnings, fresh_warns FROM players where ID = ?", [t])
        player = c.fetchone()
        
        if player is not None:
            name = player[0]
            warns = player[1] + player[2]
            stale_warns = player[1]
            fresh_warns = player[2]
            
            if int(warnings) > 0:
                if warns is None:
                    warns = 0
                
                updated_warns = max(0, fresh_warns + int(warnings))
                warn_total = stale_warns + updated_warns
                
                c.execute("UPDATE players SET fresh_warns = ? where ID = ?", [updated_warns, t])
                if user is not None:
                    await update_player_roles_util(user, warn_total)
                
                out = ctx.message.author.name + " has issued **" + warnings + "** warnings to **" + name + "** for " + reason + ". \nThey now have **" + str(warn_total) + "** warnings"
                
                if warns >= 5:
                    out += " and remain **banned**"
                elif warn_total >= 5:
                    out += " and are now **banned**"
                
                await client.say(out + ".")
                await client.send_message(warns_channel, content = out + ".")
                if ctx.message.channel.id != admin_channel.id:
                    await client.send_message(admin_channel, content = out + ".")
            else:
                await client.say("Warn amount must be positive.")
        else:
            await client.say("No user found by that name!")

        conn.commit()
        conn.close()
        
@client.command(pass_context=True, hidden=True, aliases=["rw", "removewarn", "unwarn"])
async def removewarns(ctx, name, warnings, reason):
    is_mod_channel = ctx.message.channel.id == admin_channel.id \
                  or ctx.message.channel.id == moderator_channel.id \
                  or ctx.message.channel.id == mod_discussion_channel.id

    if is_mod_channel:
        t = find_userid_by_name(ctx, name)
        if t is None:
            await client.say("No user found by that name!")
            return

        user = find_user_by_name(ctx, name)
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name, warnings, fresh_warns FROM players where ID = ?", [t])
        player = c.fetchone()
        
        if player is not None:
            name = player[0]
            warns = player[1] + player[2]
            stale_warns = player[1]
            fresh_warns = player[2]
            
            if int(warnings) > 0:
                if warns is None:
                    warns = 0
                
                if fresh_warns - int(warnings) < 0:
                    updated_fresh_warns = 0
                    updated_warns = max(0, warns - (int(warnings) - fresh_warns))
                else:
                    updated_fresh_warns = fresh_warns - int(warnings)
                    updated_warns = stale_warns
                
                warn_total = updated_warns + updated_fresh_warns
                
                c.execute("UPDATE players SET warnings = ?, fresh_warns = ? where ID = ?", [updated_warns, updated_fresh_warns, t])
                if user is not None:
                    await update_player_roles_util(user, warn_total)
                
                out = ctx.message.author.name + " has removed **" + warnings + "** warnings from **" + name + "** for " + reason + ". \nThey now have **" + str(warn_total) + "** warnings"
                
                if warn_total >= 5:
                    out += " and remain **banned**"
                elif warns >= 5:
                    out += " and are now **unbanned**"
                
                await client.say(out + ".")
                await client.send_message(warns_channel, content = out + ".")
                if ctx.message.channel.id != admin_channel.id:
                    await client.send_message(admin_channel, content = out + ".")
            else:
                await client.say("Warn amount must be positive.")
        else:
            await client.say("No user found by that name!")

        conn.commit()
        conn.close()

@client.command(pass_context=True, hidden=True)
async def modrename(ctx, name):
    is_admin_channel = ctx.message.channel.id == admin_channel.id
    if is_admin_channel:
        t = find_userid_by_name(ctx, name)
        if t is None:
            await client.say("No user found by that name!")
            return
        
        conn = sqlite3.connect(db_path)

        c = conn.cursor()
        
        A = str(ctx.message.author.id)
        B = str(ctx.message.author.name)
        
        space = str(ctx.message.content).find(" ", len(name) + 11)
        newName = str(ctx.message.content)[space + 1:]

        if len(str(newName)) < (26):
            user = find_user_by_name(ctx, name)
            if user is not None:
                await client.change_nickname(user, newName)
            
            c.execute("UPDATE players SET name = ? where ID = ?", [newName, t])
            await client.say("Rename successful.")
            # await client.change_nickname(ctx.message.author, newName + " ["+ str(elon) + "]")
        else:
            await client.say("Invalid Length.")    
        
        conn.commit()
        conn.close()


@client.command(pass_context=True, hidden=True)
async def revokerename(ctx, name):
    is_admin_channel = ctx.message.channel.id == admin_channel.id
    if is_admin_channel:
        conn = sqlite3.connect(db_path)

        c = conn.cursor()
        t = find_userid_by_name(ctx, name)
        if t is None:
            await client.say("No user found by that name!")
            conn.commit()
            conn.close()
            return
        
        c.execute("UPDATE players SET perms = perms | 1 where ID = ?", [t])
        await client.say("Revoked rename privileges from " + name + ".")
        
        conn.commit()
        conn.close()


@client.command(pass_context=True, hidden=True)
async def allowrename(ctx, name):
    is_admin_channel = ctx.message.channel.id == admin_channel.id
    if is_admin_channel:
        conn = sqlite3.connect(db_path)

        c = conn.cursor()
        
        t = find_userid_by_name(ctx, name)
        if t is None:
            await client.say("No user found by that name!")
            conn.commit()
            conn.close()
            return
        
        c.execute("UPDATE players SET perms = perms & ~1 where ID = ?", [t])
        await client.say("Granted rename privileges back to " + name + ".")
        
        conn.commit()
        conn.close()
        
@client.command(pass_context=True, hidden=True)
async def processwarns(ctx):
    is_admin_channel = ctx.message.channel.id == admin_channel.id

    if is_admin_channel:
        conn = sqlite3.connect(db_path, uri=True)
        c = conn.cursor()
        
        c.execute("SELECT ID, name, warnings, fresh_warns FROM players where warnings > 0")
        player = c.fetchone()

        output = "**Weekly warnings have been processed."
        if player is not None:
            output += " The following users have had 1 warn expire:**\n"
            space = ""
            while player is not None:
                id = player[0]
                name = player[1]
                warn_total = player[2] + player[3] - 1
                output += space + name + " *[" + str(warn_total) + "]*"
                
                server = ctx.message.server
                user = server.get_member(id)
                if user is not None:
                    await update_player_roles_util(user, warn_total)
                
                space = "    "
                player = c.fetchone()
        else:
            output += " No warnings have expired this week.**"
        
        
        
        conn.commit()
        conn.close()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute("UPDATE players SET warnings = warnings - 1 WHERE warnings > 0")
        c.execute("UPDATE players SET warnings = warnings + fresh_warns, fresh_warns = 0 WHERE fresh_warns > 0")
        conn.commit()
        conn.close()
        
        await client.say(output)
        await client.send_message(warns_channel, content = output)

        
@client.command(pass_context=True, hidden=True)
async def adjustelo(ctx, name, adjustment):
    is_admin_channel = ctx.message.channel.id == admin_channel.id
    if is_admin_channel:
        t = find_userid_by_name(ctx, name)
        if t is None:
            await client.say("No user found by that name!")
            return

        user = find_user_by_name(ctx, name)
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name, elo FROM players WHERE ID = ?", [t])
        player = c.fetchone()
        
        if player is not None:
            adjust = int(adjustment)
            name = player[0]
            elo = player[1]
            c.execute("UPDATE players SET elo = elo + ?, elo_adjustments = elo_adjustments + ? WHERE ID = ?", [adjust, adjust, t])
            
            out = "**" + ctx.message.author.name + "** has "
            if adjust > 0:
                out += "given " + adjustment + " elo to"
            else:
                out += "removed " + str(adjust * -1) + " elo from"
            out += " **" + name + "**! They now have an elo of **" + str(elo + adjust) + "**!"
            
            await client.say(out)
            await client.send_message(warns_channel, content = out)
        conn.commit()
        conn.close()
            

client.run("") #client auth key (found in discord api)

