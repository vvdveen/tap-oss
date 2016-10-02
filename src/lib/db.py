#!/usr/bin/python

import sqlite3
from features import Features

class Error(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class DatabaseError(Error):
    pass

class Database():

    def __init__(self, database):
        self.database = database

        self.open(database)
        self.create_tables()

    def open(self, database):
        self.connection = sqlite3.connect(database, timeout = 30)
        self.connection.text_factory = str
        self.cursor = self.connection.cursor()

    def close(self):
        self.cursor.close()
        self.connection.close()

    def create_tables(self):
        q_package  = "CREATE TABLE IF NOT EXISTS Package(\n" \
                   + "  md5sum       TEXT PRIMARY KEY,\n"    \
                   + "  apk          TEXT,\n" \
                   + "  logbase      TEXT)"
        q_static   = "CREATE TABLE IF NOT EXISTS  Static(\n" \
                   + "  md5sum          TEXT PRIMARY KEY,\n"   \
                   + "  package_name    TEXT,\n" \
                   + "  main_activity   TEXT,\n" \
                   + "  activities      TEXT,\n" \
                   + "  services        TEXT,\n" \
                   + "  receivers       TEXT,\n" \
                   + "  providers       TEXT,\n" \
                   + "  actions         TEXT,\n" \
                   + "  activityactions TEXT,\n" \
                   + "  categories      TEXT)"
        q_dynamic  = "CREATE TABLE IF NOT EXISTS Dynamic(\n" \
                   + "  md5sum          TEXT PRIMARY KEY, \n"  \
                   + "  ANR             INTEGER, \n" \
                   + "  died            INTEGER, \n" \
                   + "  exception       INTEGER, \n" \
                   + "  incomplete      INTEGER, \n" \
                   + "  vmcrash         INTEGER, \n" \
                   + "  f_found_naive   INTEGER, \n" \
                   + "  f_found         INTEGER, \n" \
                   + "  f_hit_naive     INTEGER, \n" \
                   + "  f_hit           INTEGER, \n" \
                   + "  cc_naive        REAL, \n" \
                   + "  cc              REAL)"
        q_features = "CREATE TABLE IF NOT EXISTS Features(\n" \
                   + "  md5sum TEXT PRIMARY KEY,\n" \
                   + "  path   TEXT"

        for field in Features().get_fields():
            if ( field[0] == 'bloom' or field[0] == 'bloom_array' or field[0] == 'package_name' or field[0] == 'average'): continue
#           if (                                                     field[0] == 'package_name'                         ): continue
            q_features = q_features + ",\n  " + field[0] + " INTEGER"
#           q_features = q_features + ",\n  " + field[0] + " TEXT"

        q_features = q_features + ")"
        
        self.cursor.execute(q_package)
        self.cursor.execute(q_static)
        self.cursor.execute(q_dynamic)
        self.cursor.execute(q_features)
        self.connection.commit()

    def insert(self, apk, logdir, static_analysis, dynamic_results, features):
        q_package = "INSERT OR REPLACE INTO Package(md5sum, apk, logbase) VALUES('" + static_analysis.md5sum + "', \
                                                                                 '" + apk + "', \
                                                                                 '" + logdir + "')"

        q_static = "INSERT OR REPLACE INTO Static VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        a_static = (     static_analysis.md5sum,
                         static_analysis.package_name,
                         static_analysis.main_activity,
                     str(static_analysis.activities),
                     str(static_analysis.services),
                     str(static_analysis.receivers),
                     str(static_analysis.providers),
                     str(static_analysis.actions),
                     str(static_analysis.activityactions),
                     str(static_analysis.categories)         )

        q_dynamic = "INSERT OR REPLACE INTO Dynamic VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        a_dynamic = (     static_analysis.md5sum,
                      int(dynamic_results.ANR),
                      int(dynamic_results.died),
                      int(dynamic_results.exception),
                      int(dynamic_results.incomplete),
                      int(dynamic_results.vmcrash),
                          dynamic_results.coverages[('complete',True) ].f_found,
#                         dynamic_results.coverages[('complete',False)].f_found,
                          dynamic_results.coverages[('complete',True) ].f_executed,
#                         dynamic_results.coverages[('complete',False)].f_executed,
                          dynamic_results.coverages[('complete',True) ].coverage,
#                         dynamic_results.coverages[('complete',False)].coverage      )
    
        q_features = "INSERT OR REPLACE INTO Features VALUES(?, ?"
        l_features = [  static_analysis.md5sum,
                        apk                     ]

        for field, value in features.get_values():
            if ( field == 'bloom' or field == 'bloom_array' or field == 'package_name' or field == 'average'): continue
#           if (                                               field == 'package_name'                      ): continue
            q_features = q_features + ", ?"
            l_features.append(str(int(value)))
#           l_features.append(str(    value ))
    
        q_features = q_features + ")"
        a_features = tuple(l_features)
      
        self.execute(q_package)
        self.execute(q_static,  a_static )
        self.execute(q_dynamic, a_dynamic)
        self.execute(q_features,a_features)
        self.connection.commit()

    def execute(self, query, parameters = None):
        try:
            if parameters: self.cursor.execute(query, parameters)
            else:          self.cursor.execute(query)
        except sqlite3.OperationalError as e:
            raise DatabaseError("Could not execute query: " + query + " (" + str(parameters) + ") . " + str(e))

