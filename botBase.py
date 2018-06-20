# -*- coding: utf-8 -*-
"""
Created on Sun Aug 13 21:36:48 2017

@author: Marker
"""

import discord
from discord.ext.commands import bot
from discord.ext import commands
import time
import random
from elo import rate_1vs1
import json
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
db_path = "/var/www/html/elo.db" #set to path of database
PLAYERS = []
results = dict()

ID = 0

LEAGUE = {}

cilent = discord.Client()
bot_prefix = "-"
client = commands.Bot(command_prefix=bot_prefix)

main_channel = discord.Object("398376440980176908") #set to copy id of a lobby channel
general = discord.Object("346494459774763009") #set to copy id of an announcement channel

@client.command(pass_context=True)
async def register(ctx):
    conn = sqlite3.connect(db_path)

    c = conn.cursor()
    
    A = str(ctx.message.author.id)
    B = str(ctx.message.author.name)
    c.execute("SELECT elo FROM players WHERE ID = ?", [A])
    mon = c.fetchone()
    if ctx.message.channel.id == general.id:
        if mon == None:
            c.execute('INSERT INTO players VALUES(?, ?, 0, 0, 1000, NULL)', [A,B])
            await client.say("You are registered!")
            await client.change_nickname(ctx.message.author, B + " (1000)")
        else:
            await client.say("You have already registered!")
    
    conn.commit()
    conn.close()

@client.command(pass_context=True)
async def lobby(ctx):
    global PLAYERS, GAME
    conn = sqlite3.connect(db_path)

    c = conn.cursor()
    
    if ctx.message.channel.id == general.id:
        if GAME:
            PLAYERS = list(set(PLAYERS))
            NAMES = []
            for t in PLAYERS:
                c.execute("SELECT name FROM players WHERE ID = ?", [t])
                name = c.fetchone()[0]
                NAMES.append(name)
            
            if len(set(PLAYERS)) > 0:
                lobbystr = "Current Lobby: "
                for t in NAMES:
                    lobbystr += t + "   "
                    
                await client.say(lobbystr)
            elif ctx.message.channel.id == general.id:
                await client.say("No lobby!")
        else:
            await client.say("No game! Please say \"-start\"")
            
    conn.close()
    
@client.command(pass_context=True)
async def join(ctx):
    global PLAYERS
    t = ctx.message.author.id
    
    conn = sqlite3.connect(db_path)

    c = conn.cursor()
    
    c.execute("SELECT currentg FROM players WHERE ID = ?", [t])
    
    A = c.fetchone()[0] == None
    if ctx.message.channel.id == general.id:
        if GAME and A:
            PLAYERS.append(ctx.message.author.id)
            await client.say("Added! " + ctx.message.author.name)
            await client.send_message(main_channel, content = ctx.message.author.name + " has signed up. (" + str(len(set(PLAYERS))) + ")")
            await client.send_message(general, content = ctx.message.author.name + " has signed up. (" + str(len(set(PLAYERS))) + ")")
        else:
            await client.say("No Game Started or Currently in Game! Please say \"-start\" or \"-r \'Team 1 Score\' \'Team 2 Score\'\".")
        
    conn.close()
    
@client.command(pass_context=True)
async def leave(ctx):
    global PLAYERS
    if ctx.message.channel.id == general.id:
        if GAME:
            try:
                PLAYERS = list(set(PLAYERS))
                PLAYERS.remove(ctx.message.author.id)
                await client.send_message(main_channel, content = ctx.message.author.name + " has removed their signup.")
                await client.send_message(general, content = ctx.message.author.name + " has removed their signup.")
            except:
                True
        else:
            await client.say("No Game Started! Please say \"-start\"")


@client.command(pass_context=True)
async def start(ctx):
    global GAME, RUNNING, PLAYERS
    if ctx.message.channel.id == general.id:
        if(not RUNNING):
            PLAYERS = []
            await client.send_message(main_channel, content = "@here\nNew Game Hosted!", tts = True)
            await client.send_message(general, content = "@here\nNew Game Hosted!", tts = True)
    
            counter = 0
            RUNNING = True
            GAME = True
            while (len(set(PLAYERS)) < 8 and counter < 90):
                await asyncio.sleep(30)
                counter += 1
                
            await client.send_message(main_channel, content = "Game Starting in 15 seconds...")
            await client.send_message(general, content = "Game Starting in 15 seconds...")
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
                sigma = 100
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
                    gameID = int(c.fetchone()[0]) + 1
                    
                    playerID = []
                    for t in ELOS:
                        playerID.append(t[0])
                        
                    
        
        
                    c.execute('INSERT INTO games VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL,NULL)', [gameID] + playerID)
                    
                    for t in playerID:
                        c.execute("UPDATE players SET currentg = ? WHERE ID = ?", [gameID, t])
                        
                    capt = 0
                    captid = ""
                    finalstr = "Team 1 (" +str(sum([int(b[1]) for b in ELOS[0:4]])) + "): "
                    for k,t in enumerate(playerID):
                        c.execute("SELECT name FROM players WHERE ID = ?", [t])
                        name = c.fetchone()[0]
                        if(capt < int(ELOS[k][1])):
                            capt = int(ELOS[k][1])
                            captid = name
                        finalstr += name + "   "
                        if k == 3:
                            finalstr += "Captain: " + captid + "\nTeam 2 (" + str(sum([int(b[1])for b in ELOS[4:8]])) +"): "
                            capt = 0
                            captid = ""
                    
                    finalstr += "Captain: " + captid + "\nTotal ELO Difference: " + str(diff) + "."
                    
                    await client.send_message(main_channel, content = finalstr)
                    await client.send_message(general, content = finalstr)
                    
                    notestr = ""
                    for t in playerID:
                        notestr += "<@" + t + "> "
                        
                    await client.send_message(main_channel, content = notestr)
                    await client.send_message(general, content = notestr)
                    
                    conn.commit()
        
                    conn.close()
                    PLAYERS = []
                else:
                    await client.send_message(main_channel, content = "Could not balance lobby.")
                    await client.send_message(general, content = "Could not balance lobby.")
                    PLAYERS = []
            else:
                await client.send_message(main_channel, content = "Not Enough Players")
                await client.send_message(general, content = "Not Enough Players")
                PLAYERS = []
                
            PLAYERS = []
            RUNNING = False
        else:
            await client.say("Game Already Started.")

@client.command(pass_context=True)
async def r(ctx):
    
    message = ctx.message.content.split()
    try:
        valid = ctx.message.channel.id == general.id and type(int(message[1])) == int and type(int(message[2])) == int
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
                            
                            await client.change_nickname(ctx.message.author, namen + " ("+ str(ELOS[k]) + ")")
                            
                            if t1g and k < 4:
                                c.execute("UPDATE players SET win = win + 1 where ID = ?", [t])
                            elif k >= 4 and not t1g:
                                c.execute("UPDATE players SET win = win + 1 where ID = ?", [t])
                            else:
                                c.execute("UPDATE players SET loss = loss + 1 where ID = ?", [t])
                                
                    c.execute("UPDATE games SET s1 = ? where ID = ?", [score[0],currentg])
                    c.execute("UPDATE games SET s2 = ? where ID = ?", [score[1],currentg])
                    
                    del results[currentg]
                        
                    await client.send_message(main_channel, content = "Game " + str(currentg) + " finished " + str(score[0]) + " - " + str(score[1]) + " with an ELO difference of +/- "
                                              + str(abs(team1diff)) + ".")
                    
                    await client.send_message(general, content = "Game " + str(currentg) + " finished " + str(score[0]) + " - " + str(score[1]) + " with an ELO difference of +/- "
                                              + str(abs(team1diff)) + ".")
                    
                
                
                except:
                    1 == 1
                    True
            
            conn.commit()

            conn.close()
        
    except:
        True
       
@client.command(pass_context=True)
async def rename(ctx):
    conn = sqlite3.connect(db_path)

    c = conn.cursor()
    
    A = str(ctx.message.author.id)
    B = str(ctx.message.author.name)
    c.execute("SELECT elo FROM players WHERE ID = ?", [A])
    mon = c.fetchone()
    if ctx.message.channel.id == general.id:
        if len(str(ctx.message.content)) < (33-7):
            c.execute("UPDATE players name = ? where ID = ?", [str(ctx.message.content), A])
            c.execute("SELECT elo FROM players where ID = ?", [A])
            elon = c.fetchone()[0]
            
            await client.change_nickname(ctx.message.author, ctx.message.content + " ("+ str(elon) + ")")
        else:
            await client.say("Invalid Length.")
        
    
    conn.commit()
    conn.close()


client.run("") #client auth key (found in discord api)