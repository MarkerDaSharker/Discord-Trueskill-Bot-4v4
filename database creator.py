# -*- coding: utf-8 -*-
"""
Created on Sat Aug 19 22:46:04 2017

@author: Marker
"""
import sqlite3

conn = sqlite3.connect('elo.db')

c = conn.cursor()

c.execute('''CREATE TABLE games (ID, p1, p2, p3, p4, p5, p6, p7, p8, s1, s2)''')

c.execute('''CREATE TABLE players (ID, name, win, loss, elo, currentg)''')


conn.commit()

conn.close()


