#!/usr/bin/env python3
###############################################################################################
#  Author: 
__author__ = '<a href="mailto:debuti@gmail.com">Borja Garcia</a>'
# Program: 
__program__ = 'myMusicNews'
# Package:
__package__ = ''
# Descrip: 
__description__ = ''''''
# Version: 
__version__ = '0.0.5'
#    Date:
__date__ = '20220207'
# License: This script doesn't require any license since it's not intended to be redistributed.
#          In such case, unless stated otherwise, the purpose of the author is to follow GPLv3.
# History: 
#          0.0.5 (20220207)
#            -Added csv output and user feedback input
#          0.0.4 (20200905)
#            -Added toml and specific excludes
#          0.0.3 (20200902)
#            -Using musicbrainzngs and py3
#          0.0.2 (20121102)
#            -Added categories
#          0.0.0 (20121102)
#            -Initial release
###############################################################################################

# Imports
import logging
import sys
import doctest
import datetime, time
import os
import argparse
import inspect
import glob
import string
import traceback
import pprint
import configparser
try:
  import toml
except:
  print("Install toml with: pip3 install toml")
  sys.exit(-1)

# Parameters, Globals n' Constants
KIBI = 1024
MEBI = 1024 * KIBI
LOG_MODE = "File"
LOG_LEVEL = logging.INFO
LOG_MAX_BYTES = 1 * MEBI

scriptPath = os.path.realpath(__file__)
scriptDirectory = os.path.dirname(scriptPath)
callingDirectory = os.getcwd()

propertiesName = __program__ + ".properties"
propertiesPath = os.path.join(scriptDirectory, '..', propertiesName) 

logFileName = __program__ + '_' + time.strftime("%Y%m%d%H%M%S") + '.log'
logDirectory = os.path.join(scriptDirectory, '..', 'logs')
logPath = os.path.join(logDirectory, logFileName)
loggerName = __package__ + "." + __program__

try:
  import musicbrainzngs
  logging.getLogger('musicbrainzngs').setLevel(logging.ERROR)
except: 
  print("Install musicbrainzngs with: pip3 install musicbrainzngs")
  sys.exit(-1)

SEP=";"

# Usage function, logs, utils and check input
def openLog(mode, desiredLevel):
    '''This function is for initialize the logging job
    '''
    def openScreenLog(formatter, desiredLevel):
        logging.basicConfig(level = desiredLevel, format = formatter)
       
    def openScreenAndFileLog(fileName, formatter, desiredLevel):
        logger = logging.getLogger('')
        logger.setLevel(desiredLevel)
        # create file handler which logs even debug messages
        fh = logging.FileHandler(fileName)
        fh.setLevel(desiredLevel)
        fh.setFormatter(formatter)
        # add the handler to logger
        logger.addHandler(fh)

    def openScreenAndRotatingFileLog(fileName, formatter, desiredLevel, maxBytes):
        logger = logging.getLogger('')
        logger.setLevel(desiredLevel)
        # create file handler which logs even debug messages
        fh = logging.handlers.RotatingFileHandler(fileName, maxBytes)
        fh.setLevel(desiredLevel)
        fh.setFormatter(formatter)
        # add the handler to logger
        logger.addHandler(fh)

    format = "%(asctime)-15s - %(levelname)-6s - %(message)s"
    formatter = logging.Formatter(format)
    # Clean up root logger
    for handler in logging.getLogger('').handlers:
        logging.getLogger('').removeHandler(handler)
    openScreenLog(format, desiredLevel)
    
    if mode == "File" or mode == "RollingFile":
        if not os.path.isdir(logDirectory):
            os.mkdir(logDirectory)
  
        if mode == "File":
            openScreenAndFileLog(logPath, formatter, desiredLevel)
    
        elif mode == "RollingFile":
            openScreenAndRotatingFileLog(logPath, formatter, desiredLevel, LOG_MAX_BYTES)

            
def closeLog():
    '''This function is for shutdown the logging job
    '''
    logging.shutdown()

    
def checkInput():
    '''This function is for treat the user command line parameters.
    '''
    def is_folder(string):
      if os.path.isdir(string):
        return string
      else:
        raise Exception("Path is not a folder")

    p = argparse.ArgumentParser(description=__description__,
                                prog=__program__,
                                usage='''''') 
    p.add_argument('--album-folder', '-a', action="store", type=is_folder,
                   dest="albumpath", required=True,  help="Path for albums")

    subparsers = p.add_subparsers(help='Sub-command help', dest='command', required=True)

    process_subparser = subparsers.add_parser("process", description="Process the music collection")
    process_subparser.add_argument('--csv-output',   '-c', action="store", type=argparse.FileType('w'), 
                                   dest="csvoutput", required=False, help="Output given by the software")

    update_subparser = subparsers.add_parser("update", description="Update the user preferences")
    update_subparser.add_argument('--csv-input',   '-c', action="store", type=argparse.FileType('r'),
                                  dest="csvinput", required=True, help="Input, with user preferences for each album")

    return p.parse_args()

def getReleaseGroups(artistId, type = 'all'):
    ''' Return selected releases as in tuples [name, year, type, id]
    '''
    result = []
    
    if type == 'all':
        release_type=["album"]
    if type == 'live':
        release_type=["live"]
    if type == 'comp':
        release_type=["compilation"]

    artist = musicbrainzngs.get_artist_by_id(artistId, includes=['release-groups'], release_type=release_type)
    #pprint.pprint(artist)
  
    if artist["artist"]["release-group-count"] > 0:
      for releaseGroup in artist["artist"]["release-group-list"]:
         result.append({'title' : releaseGroup['title'], 
                        'date'  : releaseGroup['first-release-date'] if releaseGroup['first-release-date'] != '' else None,
                        'type'  : releaseGroup['type'],
                        'id'    : releaseGroup['id'],
                        'fname' : sanitizeFilename(releaseGroup['title'])})
        
    return result

def sanitizeFilename(filename, repl='_'):
  ''' Accept a unicode string, and return a normal string (bytes in Python 3)'''
  import string
  valid_chars = "-_() %s%s" % (string.ascii_letters, string.digits)
  return ''.join((c if c in valid_chars else repl) for c in filename)
    
def getGroupreleasesByArtist(diskArtist, type = 'all'):
    ''' Return group releases (groups of similar releases: different number of tracks, country, etc)
    '''
    result = []
    
    # Search for the artist
    artists = musicbrainzngs.search_artists(diskArtist)
    #pprint.pprint(artists)
    if artists is None or artists['artist-count']<=0:
      logging.error(' Artist not found')
      return result

    artist = max(filter(lambda x: int(x['ext:score'])>60, 
                        artists['artist-list']), 
                 key = lambda x: int(x['ext:score']))
    #pprint.pprint(artist)
              
    # Search for releases
    releaseGroups = getReleaseGroups(artist['id'], type)
    if len(releaseGroups) == 0:
      logging.info(" No release groups found for this artist")
    else:
      result = releaseGroups
                
    return result
      
    
def checkMissingAlbums(args):
    '''
    '''
    def csvappend(f, info):
      TPL="\"{artist}\"{SEP}\"{title}\"{SEP}\"{date}\"{SEP}\"{rtype}\"{SEP}\"{status}\"\n"
      if not hasattr(csvappend, "init"): 
        f.write("SEP={SEP}\n".format(SEP=SEP))
        f.write(TPL.format(artist="Artist", title="Title", status="Status [found, not-found, excluded]", rtype="Release type", date="Date", SEP=SEP))
        csvappend.init=True
      for status in ['found', 'not-found', 'excluded']:
        for album in info['findings'][status]:
          f.write(TPL.format(artist=info['artist'], title=album['title'], rtype=album['type'], date=album['date'], status=status, SEP=SEP))

    for diskArtist in sorted([name for name in os.listdir(args.albumpath) if os.path.isdir(os.path.join(args.albumpath, name))]):
        artistpath = os.path.join(args.albumpath, diskArtist)
        process = True
        excludes = []

        logging.info("")
        logging.info("Working on local " + diskArtist) 

        if os.path.isfile(os.path.join(artistpath, "artist.toml")):
          config = toml.load(os.path.join(artistpath, "artist.toml"))
          if "musicNews" in config:
            if "skip" in config["musicNews"]:
              process = not (config["musicNews"]["skip"]) 
            if "excludes" in config["musicNews"]:
              excludes = config["musicNews"]["excludes"]

        if process:
            releaseGroups = getGroupreleasesByArtist(diskArtist)
            logging.info(" Found " + str(len(releaseGroups)) + " release groups")
                        
            categories = {'found':[], 'not-found':[], 'excluded':[]}

            localReleases = list(map(lambda x: sanitizeFilename(x), 
                                     [name for name in os.listdir(artistpath) if os.path.isdir(os.path.join(artistpath, name))]))

            for releaseGroup in releaseGroups:
                found = False
                if releaseGroup['title'] in excludes:
                  logging.info("  * Release {} skipped".format(releaseGroup["title"]))
                  categories['excluded'].append(releaseGroup)
                  continue

                for localDiskRelease in localReleases:
                    if releaseGroup['fname'] in localDiskRelease:
                        found = True
                        break
                    
                if found:
                    categories['found'].append(releaseGroup)
                else:
                    categories['not-found'].append(releaseGroup)

            if args.csvoutput:
              csvappend(args.csvoutput, {'artist': diskArtist, 'path': artistpath, 'findings':categories})
            
            if len(categories['not-found']) > 0:
              logging.info("  - You DON'T have these albums")
              for item in sorted(categories['not-found'], key=lambda x: x['type']):
                logging.info((" "*3 + "-> " if item['type'] == "Album" else " "*6) + diskArtist + " - "+ item['title'] + (" as of " + item['date'] if item['date'] is not None else ""))
                    
            time.sleep(5) #Prevent 503 error by waiting 5 seconds (as 50 request per second are allowed)
        else:
            logging.info(" Skipped")
            
def updatePreferences(args):
  from itertools import groupby
  fields = ["artist", "title", "date", "rtype", "status"]
  allalbums = [dict(zip(fields, [x.strip("\"") for x in line.strip().split(SEP)])) for line in args.csvinput.readlines()[2:]]
  for artist, allartistalbums in groupby(sorted(allalbums, 
                                                key=lambda x: x['artist']),
                                         key=lambda x: x['artist']):
    shouldwrite = False
    statuses = {k: list(v) for k, v in groupby(sorted(allartistalbums,
                                                      key=lambda x: x['status']),
                                               key=lambda x: x['status'])}
    artistpath = os.path.join(args.albumpath, artist)
    prefpath = os.path.join(artistpath, "artist.toml")
    if not os.path.isfile(prefpath):
      config = {'musicNews' : {'skip':False, 'excludes':[]}}
    else:
      config = toml.load(prefpath)
      if not "musicNews" in config:
        raise Exception("Malformed artist.toml in {}".format(album['artist']))
      
    if len(config['musicNews']['excludes']) > 0 and "excluded" not in statuses:
      config['musicNews']['excludes'] = []
      shouldwrite = True
      
    if 'excluded' in statuses:
      config['musicNews']['excludes'] = [album['title'] for album in statuses["excluded"]]
      shouldwrite = True
    
    if shouldwrite:
      tomls = pprint.pformat(config, indent=4)
      logging.info(tomls)
      with open(prefpath, "w") as tomlf:
        toml.dump(config, tomlf)
    
def core(args):
    '''This is the core, all program logic is performed here
    '''
    if args.command == "process":
      checkMissingAlbums(args)
      #TODO: checkNewArtist(albumpath)
    elif args.command == "update":
      updatePreferences(args)
    else:
      raise Exception("Unknown command")


# Main function
def main():
    '''This is the main procedure, is detached to provide compatibility with the updater
    '''
    openLog(LOG_MODE, LOG_LEVEL)
    args = checkInput()
    musicbrainzngs.set_useragent(__program__, __version__)
    core(args)
    closeLog()


# Entry point
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print ("Shutdown requested. Exiting")
    except UnicodeDecodeError as e:
        print ("UnicodeDecodeError: " + e.reason + " on string \"" + e.object + "\" positions: " + str(e.start) + "-" + str(e.end))
        print (traceback.format_exc())
    except UnicodeEncodeError as e:
        print ("UnicodeEncodeError: " + e.reason + " on string \"" + e.object + "\" positions: " + str(e.start) + "-" + str(e.end))
        print (traceback.format_exc())
    
