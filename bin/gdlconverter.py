# -*- coding: utf-8 -*-
"""
GDL Converter Tool - für die Konvertierung zwischen GSM, XML, HSF und LCF Formaten
Handhabt die Umwandlung von ArchiCAD GDL-Bibliothekselementen zwischen verschiedenen Formaten
und unterstützt Backup- und Dokumentationsfunktionen.
"""
import datetime
import os
import shutil
import glob
import codecs
import sys
import xml.etree.ElementTree as ET
import csv
import platform
import logging
from subprocess import call, run
from os.path import join as pjoin, isdir
from xml.dom.minidom import parse, parseString
from xml.parsers.expat import ExpatError, ErrorString
from mimetypes import MimeTypes
import json

# Globale Konfigurationsvariable
C = None

# Konstanten für Ordnerstrukturen
# FOLDER_GSM_SOURCE: Quell-GSM-Dateien (01_gsms)
# FOLDER_GSM_WORK: Arbeitsverzeichnis für Konvertierungen (06_library_gsm)
FOLDER_GSM_BASE = '01_gsms'
FOLDER_SOURCE = '02_source'
FOLDER_BITMAPS = '03_bitmaps'
FOLDER_DOCUMENTATION = '04_documentation'
FOLDER_XML_LIBRARY = '05_library_xml'
FOLDER_XML_OUT = '05_library_xml/out'
FOLDER_GSM_WORK = '06_library_gsm'
FOLDER_HSF = '07_hsf'
FOLDER_XML_BACKUPS = '14_XML_Backups'
FOLDER_LOGS = '16_logs'

# Diese werden nach dem Laden der Konfiguration initialisiert
GSM_LIBRARY_NAME = None
FOLDER_GSM_SOURCE = None
FOLDERS_GSMS = None
project_path = None
ziel = None
quelle = None
logger = None

# Debugging-Option
PRINT_TIMES = 1

# XML-Tags für Quell-XML-Dateien
XMLTAG_SOURCEXML = {
  'Parameters.xml': 'ParamSection',
  'Picture.xml': 'Picture',
  'GDLPict.xml': 'GDLPict',
}

# XML-Tags für Quellskripte
XMLTEXT_SOURCETEXT = {
  '1-Master-Script.gdl': 'Script_1D',
  '2-Parameter-Script.gdl': 'Script_VL',
  '3-2D-Script.gdl': 'Script_2D',
  '4-3D-Script.gdl': 'Script_3D',
  '5-Interface-Script.gdl': 'Script_UI',
  '6-Properties-Script.gdl': 'Script_PR',
  '7-Forward-Script.gdl': 'Script_FWM',
  '8-Backward-Script.gdl': 'Script_BWM',
}


def setup_logging(projectpath):
    """
    Initialisiert das Logging-System.
    
    Args:
        projectpath: Pfad zum Projektverzeichnis
        
    Returns:
        Logger-Instanz
    """
    global logger
    
    log_dir = pjoin(projectpath, FOLDER_LOGS)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = pjoin(log_dir, f'gdlconverter_{datetime.datetime.now().strftime("%Y%m%d")}.log')
    
    # Logger konfigurieren
    logger = logging.getLogger('gdlconverter')
    logger.setLevel(logging.DEBUG)
    
    # Handler für Datei (DEBUG und höher)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    # Handler für Konsole (INFO und höher)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    
    # Handler hinzufügen
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def detect_library_name(projectpath):
    """
    Ermittelt den Bibliotheksnamen automatisch aus dem ersten Ordnernamen unter 01_gsms/.
    Ignoriert Ordner mit "-Demo" Suffix.
    
    Args:
        projectpath: Pfad zum Projektverzeichnis
        
    Returns:
        Bibliotheksname oder None wenn nicht gefunden
    """
    gsm_base_path = pjoin(projectpath, FOLDER_GSM_BASE)
    
    if not os.path.exists(gsm_base_path):
        return None
    
    # Alle Ordner unter 01_gsms/ auflisten
    folders = [f for f in os.listdir(gsm_base_path) 
               if isdir(pjoin(gsm_base_path, f)) and not f.startswith('.')]
    
    # Sortieren und den ersten Ordner ohne "-Demo" Suffix nehmen
    folders.sort()
    for folder in folders:
        if not folder.endswith('-Demo'):
            return folder
    
    # Falls nur Demo-Ordner vorhanden, den ersten nehmen und "-Demo" entfernen
    if folders:
        return folders[0].replace('-Demo', '')
    
    return None


def gsm_backups(file2backup, filename):
    """
    Erstellt Backups einer GSM-Datei in konfigurierten Backup-Verzeichnissen.
    
    Args:
        file2backup: Pfad zur zu sichernden Datei
        filename: Dateiname ohne Pfad und Erweiterung
    """
    if 'gsmbackupdirectories' not in C:
        error_msg = 'No GSM backup directories ("gsmbackupdirectories") defined in gdlconfig.json! If no backups are needed, use this:\n"gsmbackupdirectories: []'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
        
    for backupdirectory in C['gsmbackupdirectories']:
        if 'directory' not in backupdirectory or 'filename' not in backupdirectory:
            error_msg = 'GSM backup directory configuration ("gsmbackupdirectories") defined in gdlconfig.json is missing "directory" or "filename" key!'
            if logger:
                logger.warning(error_msg)
            print(error_msg)
            continue
            
        backupfolder = backupdirectory['directory'].replace('{$projectpath}', C['projectpath'])
        backupfilename = backupdirectory['filename'].replace('{$filename}', filename)
        
        # Ersetze Zeitplatzhalter falls vorhanden
        if 'strftime' in backupdirectory:
            backupstrftime = datetime.datetime.now().strftime(backupdirectory['strftime'])
            backupfolder = backupfolder.replace('{$strftime}', backupstrftime)
            backupfilename = backupfilename.replace('{$strftime}', backupstrftime)
            
        # Erstelle Backup-Verzeichnis falls nötig
        if not os.path.exists(backupfolder):
            os.makedirs(backupfolder)
            
        # Kopiere die Datei ins Backup-Verzeichnis
        try:
            shutil.copy(file2backup, pjoin(backupfolder, backupfilename))
            if logger:
                logger.debug(f'Backup erstellt: {pjoin(backupfolder, backupfilename)}')
        except Exception as e:
            error_msg = f'Fehler beim Erstellen des Backups: {e}'
            if logger:
                logger.error(error_msg)
            print(error_msg)


def format_timedelta(td):
    """
    Formatiert ein timedelta-Objekt als lesbare Zeichenkette.
    
    Args:
        td: Ein datetime.timedelta Objekt
        
    Returns:
        Formatierte Zeit in Sekunden
    """
    return str(td.seconds+td.microseconds/1000000.0)+'s'


def git_commit_source(projectpath, mode, filename):
    """
    Erstellt einen Git-Commit der 02_source/ Dateien nach einer Konvertierung.

    Args:
        projectpath: Pfad zum Projektverzeichnis (= Git-Root)
        mode:        Konvertierungsrichtung, z.B. 'g2x' oder 'x2g'
        filename:    Name des verarbeiteten GDL-Objekts (ohne Erweiterung)
    """
    msg = f'{mode}: {filename}'
    try:
        # Alle geänderten Quelldateien stagen
        stage = run(
            ['git', 'add', FOLDER_SOURCE],
            cwd=projectpath, capture_output=True, text=True
        )
        if stage.returncode != 0:
            warn = f'Git add fehlgeschlagen: {stage.stderr.strip()}'
            if logger: logger.warning(warn)
            print(warn)
            return

        # Prüfen ob es tatsächlich etwas zu committen gibt
        status = run(
            ['git', 'status', '--porcelain', FOLDER_SOURCE],
            cwd=projectpath, capture_output=True, text=True
        )
        if not status.stdout.strip():
            info = f'Git: Keine Änderungen in {FOLDER_SOURCE} – kein Commit nötig.'
            if logger: logger.info(info)
            print(info)
            return

        commit = run(
            ['git', 'commit', '-m', msg],
            cwd=projectpath, capture_output=True, text=True
        )
        if commit.returncode == 0:
            info = f'Git-Commit erstellt: "{msg}"'
            if logger: logger.info(info)
            print(info)
        else:
            warn = f'Git commit fehlgeschlagen: {commit.stderr.strip()}'
            if logger: logger.warning(warn)
            print(warn)
    except Exception as e:
        warn = f'Git-Integration nicht verfügbar: {e}'
        if logger: logger.warning(warn)
        print(warn)


def parse_generated_xml(originalxmlfile):
    """
    Parst eine XML-Datei und bereitet sie für die Verarbeitung vor.
    
    Args:
        originalxmlfile: Pfad zur XML-Datei
        
    Returns:
        DOM-Objekt der XML-Datei
        
    Raises:
        SystemExit: Wenn die XML-Datei nicht gelesen werden kann
    """
    try:
        with codecs.open(originalxmlfile, 'r', encoding='utf-8-sig') as f:
            xml = f.read()
    except Exception as e:
        error_msg = f'Error trying to read {originalxmlfile}! {str(e)}'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
        
    # Verhindert Entfernung leerer CDATA-Abschnitte durch minidom
    xml = xml.replace('<![CDATA[]]>', '<![CDATA[" "]]>')
    return parseString(xml)


def replace_with_source(originalxmlfile, sourcefolder):
    """
    Ersetzt Teile einer XML-Datei mit Inhalten aus Quelldateien.
    
    Args:
        originalxmlfile: Pfad zur originalen XML-Datei
        sourcefolder: Verzeichnis mit den Quelldateien
        
    Returns:
        Die aktualisierte XML als String
        
    Raises:
        SystemExit: Bei XML-Parsing-Fehlern oder wenn Quelldateien nicht gelesen werden können
    """
    root = parse_generated_xml(originalxmlfile)
    symbol = root.childNodes[0]
    
    # XML-Elemente ersetzen
    for sourcefilename, xmltag in XMLTAG_SOURCEXML.items():
        oldelements = symbol.getElementsByTagName(xmltag)
        try:
            with open(pjoin(sourcefolder, sourcefilename), 'r', encoding='utf-8') as f:
                rawxml = f.read()
        except Exception as e:
            error_msg = f'Error trying to read {sourcefilename}! {str(e)}'
            if logger:
                logger.error(error_msg)
            print(error_msg)
            sys.exit(1)
            
        sourcexml = '<root>'+rawxml+'</root>'
        try:
            sourceroot = parseString(sourcexml)
        except ExpatError as e:
            error_msg = f'XML in {sourcefilename} could not be parsed! {ErrorString(e.code)}'
            if logger:
                logger.error(error_msg)
                lines = rawxml.splitlines()
                for lineno in range(e.lineno-4, e.lineno+3):
                    if lineno>=0 and lineno<len(lines):
                        if lineno==e.lineno-1:
                            logger.error(f'* {lineno} {lines[lineno]}')
                        else:
                            logger.debug(f'  {lineno} {lines[lineno]}')
            print(error_msg)
            lines = rawxml.splitlines()
            for lineno in range(e.lineno-4, e.lineno+3):
                if lineno>=0 and lineno<len(lines):
                    if lineno==e.lineno-1:
                        print('*', lineno, lines[lineno])
                    else:
                        print(' ', lineno, lines[lineno])
            sys.exit(1)
            
        # Füge neue Elemente ein und entferne alte
        for el in sourceroot.firstChild.childNodes:
            if len(oldelements):
                symbol.insertBefore(el, oldelements[0])
            else:
                symbol.appendChild(el)
                
        for oldelement in oldelements:
            symbol.removeChild(oldelement)
    
    # Skript-Teile ersetzen
    for sourcefilename, xmltag in XMLTEXT_SOURCETEXT.items():
        tags = symbol.getElementsByTagName(xmltag)
        if not tags:
            # XML enthaelt dieses Skript-Tag nicht (z.B. Label-Objekt ohne 3D-Skript)
            # -> ueberspringen statt Crash mit IndexError
            continue
        tag = tags[0]
        while len(tag.childNodes)>0:
            tag.removeChild(tag.childNodes[0])
        try:
            with open(pjoin(sourcefolder, sourcefilename), 'r', encoding='utf-8') as f:
                script_content = f.read()
        except Exception as e:
            error_msg = f'Error trying to read {sourcefilename}! {str(e)}'
            if logger:
                logger.error(error_msg)
            print(error_msg)
            sys.exit(1)

        cdata = root.createCDATASection(script_content)
        tag.appendChild(cdata)
        
    return symbol.toxml()


def write_source(originalxmlfile, sourcefolder):
    """
    Extrahiert Quellcode aus einer XML-Datei und schreibt ihn in separate Dateien.
    
    Args:
        originalxmlfile: Pfad zur XML-Datei
        sourcefolder: Zielordner für die extrahierten Quellen
    """
    root = parse_generated_xml(originalxmlfile)
    
    # XML-Teile extrahieren
    for sourcefilename, xmltag in XMLTAG_SOURCEXML.items():
        write_source_xml(pjoin(sourcefolder, sourcefilename), root, xmltag)
    
    # Skript-Teile extrahieren
    for sourcefilename, xmltag in XMLTEXT_SOURCETEXT.items():
        write_source_script(pjoin(sourcefolder, sourcefilename), root, xmltag)


def write_source_xml(sourcefilename, root, xmltag):
    """
    Extrahiert XML-Inhalte aus einem DOM-Baum und schreibt sie in eine Datei.
    
    Args:
        sourcefilename: Zieldatei für die XML-Inhalte
        root: DOM-Baum, aus dem extrahiert wird
        xmltag: Name des zu extrahierenden XML-Tags
    """
    start = datetime.datetime.now()
    xml = ''
    elements = root.getElementsByTagName(xmltag)
    for e in elements:
        xml += e.toxml()+'\n'
    try:
        with open(sourcefilename, 'w', encoding='utf-8') as f:
            f.write(xml)
        if PRINT_TIMES:
            time_str = format_timedelta(datetime.datetime.now()-start)
            print('Write XML:', xmltag, 'time:', time_str)
            if logger:
                logger.debug(f'Write XML: {xmltag} time: {time_str}')
    except Exception as e:
        error_msg = f'Error writing {sourcefilename}: {str(e)}'
        if logger:
            logger.error(error_msg)
        print(error_msg)


def write_source_script(sourcefilename, root, xmltag):
    """
    Extrahiert GDL-Skript aus einem DOM-Baum und schreibt es in eine Datei.
    
    Args:
        sourcefilename: Zieldatei für das GDL-Skript
        root: DOM-Baum, aus dem extrahiert wird
        xmltag: Name des zu extrahierenden Skript-Tags
    """
    start = datetime.datetime.now()
    scripts = root.getElementsByTagName(xmltag)
    if not scripts:
        # GSM enthaelt dieses Skript-Tag nicht (z.B. Objekt ohne 3D-/Properties-Skript)
        # -> ueberspringen statt Crash mit IndexError
        if logger:
            logger.debug(f'Skript-Tag {xmltag} nicht vorhanden -> uebersprungen')
        return
    script = scripts[0]
    code = ''
    for node in script.childNodes:
        if node.nodeType==node.CDATA_SECTION_NODE:
            code += node.data
    if code.strip('" ')=='':
        code = '! '+xmltag
    try:
        with open(sourcefilename, 'w', encoding='utf-8') as f:
            f.write(code)
        if PRINT_TIMES:
            time_str = format_timedelta(datetime.datetime.now()-start)
            print('Write Script:', xmltag, 'time:', time_str)
            if logger:
                logger.debug(f'Write Script: {xmltag} time: {time_str}')
    except Exception as e:
        error_msg = f'Error writing {sourcefilename}: {str(e)}'
        if logger:
            logger.error(error_msg)
        print(error_msg)


def get_lpxmlconverter_path():
    """
    Ermittelt den Pfad zum LP_XMLConverter basierend auf Plattform und Konfiguration.
    
    Returns:
        Pfad zum LP_XMLConverter oder None wenn nicht gefunden
    """
    # Zuerst prüfen ob direkt in Konfiguration definiert
    if 'lpxmlconverter' in C and C['lpxmlconverter']:
        converter_path = C['lpxmlconverter']
        if os.path.exists(converter_path) and os.access(converter_path, os.X_OK):
            return converter_path
    
    # Plattform-spezifische Pfadauswahl
    system = platform.system().lower()
    # Hinweis: platform.system() gibt auf macOS "Darwin" zurueck,
    # die gdlconfig.json verwendet jedoch "mac" als Schluessel.
    if system == 'darwin':
        system = 'mac'
    if 'platforms' in C and system in C['platforms']:
        platform_config = C['platforms'][system]
        if 'lpxmlconverter' in platform_config:
            converter_path = platform_config['lpxmlconverter']
            if os.path.exists(converter_path) and os.access(converter_path, os.X_OK):
                return converter_path
    
    return None


def lpxmlconverter(mode, filename, *args):
    """
    Führt den lpxmlconverter mit den angegebenen Parametern aus.
    
    Args:
        mode: Konvertierungsmodus (l2x, x2l, etc.)
        filename: Zu verarbeitender Dateiname
        *args: Zusätzliche Argumente für den Konverter
        
    Returns:
        Exit-Code des Konverter-Prozesses
    """
    start = datetime.datetime.now()
    args = list(args)
    
    # Passwort hinzufügen, falls konfiguriert
    if 'passwords' in C and filename in C['passwords']:
        args = ['-password', C['passwords'][filename]] + args
    
    # Pfad zum Konverter ermitteln
    converter_path = get_lpxmlconverter_path()
    if not converter_path:
        error_msg = 'Error: lpxmlconverter path not found. Please check gdlconfig.json'
        if logger:
            logger.error(error_msg)
            logger.error(f'Current platform: {platform.system()}')
            logger.error('Checked paths:')
            if 'lpxmlconverter' in C:
                logger.error(f'  - {C["lpxmlconverter"]}')
            if 'platforms' in C:
                for plat, config in C['platforms'].items():
                    if 'lpxmlconverter' in config:
                        logger.error(f'  - {plat}: {config["lpxmlconverter"]}')
        print(error_msg)
        print(f'  Current platform: {platform.system()}')
        print(f'  Checked paths:')
        if 'lpxmlconverter' in C:
            print(f'    - {C["lpxmlconverter"]}')
        if 'platforms' in C:
            for plat, config in C['platforms'].items():
                if 'lpxmlconverter' in config:
                    print(f'    - {plat}: {config["lpxmlconverter"]}')
        return 1
        
    args = [converter_path, mode] + args
    if logger:
        logger.info(f'Execute: {" ".join(args)}')
    print('Execute', args)
    exitcode = call(args)
    if PRINT_TIMES:
        time_str = format_timedelta(datetime.datetime.now()-start)
        print('Execute time:', time_str)
        if logger:
            logger.debug(f'Execute time: {time_str}')
    return exitcode


def lcflpxmlconverter(mode, ziel, quelle):
    """
    Führt den LP_XMLConverter mit dem angegebenen Modus, Zielort und Quellort aus.
    
    Args:
        mode (str): Der Modus des LP_XMLConverter.
        ziel (str): Der Zielort der LCF-Datei.
        quelle (str): Der Quellort des Library-Verzeichnisses.
        
    Returns:
        Exit-Code des Konverter-Prozesses
    """
    start = datetime.datetime.now()
    
    # Pfad zum Konverter ermitteln
    converter_path = get_lpxmlconverter_path()
    if not converter_path:
        error_msg = 'Error: lpxmlconverter path not found. Please check gdlconfig.json'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        return 1
        
    # Erstelle die Befehlsliste für den Aufruf des LP_XMLConverter
    command = [converter_path, mode, ziel, quelle] 
    
    # Drucke den auszuführenden Befehl
    if logger:
        logger.info(f'Execute: {" ".join(command)}')
    print('Execute', command)
    
    # Führe den Befehl aus und erhalte den Exitcode
    try:
        exitcode = call(command)
    except Exception as e:
        error_msg = f"Error executing command: {e}"
        if logger:
            logger.error(error_msg, exc_info=True)
        print(error_msg)
        exitcode = -1  # Setze den Exitcode auf -1 im Falle eines Fehlers
        
    if PRINT_TIMES:
        time_str = format_timedelta(datetime.datetime.now()-start)
        print('Execute time:', time_str)
        if logger:
            logger.debug(f'Execute time: {time_str}')
    return exitcode


def convert_to_lcf():
    """
    Konvertiert ein Library-Verzeichnis in eine LCF-Datei.
    Verwendet globale Variablen ziel und quelle für die Pfadangaben.
    """
    global ziel, quelle
    
    # Erstelle den Zielordner, falls er nicht existiert
    target_dir = os.path.dirname(ziel)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        if logger:
            logger.debug(f'Created LCF target directory: {target_dir}')
        
    if logger:
        logger.info(f"Converting library to LCF: {quelle} -> {ziel}")
    print(f"Converting library to LCF: {quelle} -> {ziel}")
    return lcflpxmlconverter('createcontainer', ziel, quelle)

def convert_svg_to_tiff():
    """
    Konvertiert SVG-Dateien in TIFF-Format unter Ausschluss der SVG-Ordner.
    Verwendet LP_XMLConverter mit convertlibrary -excludesvg.
    """
    svg_folder = pjoin(project_path, '25_SVG')
    tiff_folder = pjoin(project_path, '26_TIFF')
    
    # Erstelle TIFF-Ordner, falls er nicht existiert
    if not os.path.exists(tiff_folder):
        os.makedirs(tiff_folder)
        if logger:
            logger.debug(f'Created TIFF target directory: {tiff_folder}')
    
    # Prüfe ob SVG-Ordner existiert
    if not os.path.exists(svg_folder):
        error_msg = f"SVG folder not found: {svg_folder}"
        if logger:
            logger.error(error_msg)
        print(error_msg)
        return 1
        
    if logger:
        logger.info(f"Converting SVG to TIFF: {svg_folder} -> {tiff_folder}")
    print(f"Converting SVG to TIFF: {svg_folder} -> {tiff_folder}")
    
    # Pfad zum Konverter ermitteln
    converter_path = get_lpxmlconverter_path()
    if not converter_path:
        error_msg = 'Error: lpxmlconverter path not found. Please check gdlconfig.json'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        return 1
    
    # Erstelle die Befehlsliste
    command = [converter_path, 'convertlibrary', '-excludesvg', svg_folder, tiff_folder]
    
    # Führe den Befehl aus
    if logger:
        logger.info(f'Execute: {" ".join(command)}')
    print('Execute', command)
    
    start = datetime.datetime.now()
    try:
        exitcode = call(command)
    except Exception as e:
        error_msg = f"Error executing command: {e}"
        if logger:
            logger.error(error_msg, exc_info=True)
        print(error_msg)
        exitcode = -1
    
    if PRINT_TIMES:
        time_str = format_timedelta(datetime.datetime.now()-start)
        print('Execute time:', time_str)
        if logger:
            logger.debug(f'Execute time: {time_str}')
    
    if logger:
        if exitcode == 0:
            logger.info(f"SVG to TIFF conversion successful")
        else:
            logger.error(f"SVG to TIFF conversion failed with exit code: {exitcode}")
    
    return exitcode

def gsm2hsf(gsmfile):
    """
    Konvertiert eine GSM-Datei ins HSF-Format.
    
    Args:
        gsmfile: Pfad zur GSM-Datei
    """
    filename = os.path.splitext(os.path.basename(gsmfile))[0]
    infolder = pjoin(C['projectpath'], FOLDER_GSM_WORK, filename)
    xmlfilename = pjoin(C['projectpath'], FOLDER_XML_LIBRARY, filename, filename+'.xml')
    sourcefolder = pjoin(C['projectpath'], FOLDER_HSF, filename)
    backupfolder = pjoin(C['projectpath'], FOLDER_XML_BACKUPS)
    
    # Backup erstellen, falls die XML-Datei existiert
    if not os.path.exists(backupfolder):
        os.makedirs(backupfolder)
    if os.path.exists(xmlfilename):
        shutil.copy(xmlfilename, pjoin(backupfolder, filename+datetime.datetime.now().strftime('_%Y_%m_%d_%H_%M')+'.xml'))
    
    # GSM-Datei kopieren
    if not os.path.exists(infolder):
        os.makedirs(infolder)
    shutil.copy(gsmfile, infolder)
    
    # Konvertierung durchführen
    lpxmlconverter('l2hsf', filename,
            pjoin(C['projectpath'], FOLDER_GSM_WORK, filename),
            pjoin(C['projectpath'], FOLDER_HSF, filename))
    
    # Quellcodedateien extrahieren — nur wenn eine XML vorliegt (z. B. nach
    # vorherigem g2x). GSM2HSF funktioniert auch ohne: l2hsf erzeugt die
    # HSF-Dateien direkt. Bestehendes Verhalten (XML vorhanden) bleibt gleich.
    if os.path.exists(xmlfilename):
        if not os.path.exists(sourcefolder):
            os.makedirs(sourcefolder)
        write_source(xmlfilename, sourcefolder)
    git_commit_source(C['projectpath'], 'l2hsf', filename)


def hsf2gsm(gsmfile):
    """
    Konvertiert HSF-Quelldateien zurück in eine GSM-Datei.
    LP_XMLConverter erstellt immer Unterordner - wir verschieben die GSM direkt.
    
    Args:
        gsmfile: Pfad zur Ziel-GSM-Datei
    """
    filename = os.path.splitext(os.path.basename(gsmfile))[0]
    hsf_base_folder = pjoin(C['projectpath'], FOLDER_HSF)
    gsm_target_folder = os.path.dirname(gsmfile)
    
    # Prüfen ob HSF-Ordner für diese Datei existiert
    hsf_file_folder = pjoin(hsf_base_folder, filename)
    if not os.path.exists(hsf_file_folder):
        error_msg = f'HSF folder not found: {hsf_file_folder}'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        return 1
    
    # Backup der bestehenden GSM-Datei erstellen
    file2backup = pjoin(C['projectpath'], FOLDER_GSM_WORK, filename, filename+'.gsm')
    if os.path.exists(file2backup):
        gsm_backups(file2backup, filename)
    
    # In temporären Ordner konvertieren (LP_XMLConverter erstellt Unterordner)
    temp_output_folder = pjoin(C['projectpath'], FOLDER_GSM_WORK, 'temp_hsf2l')
    if os.path.exists(temp_output_folder):
        shutil.rmtree(temp_output_folder)
    os.makedirs(temp_output_folder)
    
    # Konvertierung durchführen mit hsf2l Modus (konvertiert alle HSF-Dateien)
    if logger:
        logger.info(f'Converting HSF to GSM: {hsf_base_folder} -> {temp_output_folder}')
    print(f'Converting HSF to GSM: {hsf_base_folder} -> {temp_output_folder}')
    
    exitcode = lpxmlconverter('hsf2l', filename,
            hsf_base_folder,
            temp_output_folder)
    
    if exitcode == 0:
        # LP_XMLConverter erstellt: temp_hsf2l/{filename}/{filename}.gsm
        # Wir wollen: 06_library_gsm/{filename}/{filename}.gsm
        created_subfolder = pjoin(temp_output_folder, filename)
        created_gsm = pjoin(created_subfolder, filename + '.gsm')
        target_folder = pjoin(C['projectpath'], FOLDER_GSM_WORK, filename)
        target_gsm = pjoin(target_folder, filename + '.gsm')
        
        if os.path.exists(created_gsm):
            # Erstelle Zielordner falls nötig
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)
            
            # Verschiebe die GSM in den Zielordner
            shutil.move(created_gsm, target_gsm)
            if logger:
                logger.info(f'Successfully converted HSF to GSM: {target_gsm}')
        else:
            error_msg = f'GSM file not found at: {created_gsm}'
            if logger:
                logger.error(error_msg)
            print(error_msg)
            exitcode = 1
        
        # Temporären Ordner aufräumen
        if os.path.exists(temp_output_folder):
            shutil.rmtree(temp_output_folder)
    else:
        error_msg = 'HSF2GSM conversion failed!'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        
        # Temporären Ordner aufräumen
        if os.path.exists(temp_output_folder):
            shutil.rmtree(temp_output_folder)
    
    return exitcode


def gsm2xml(gsmfile):
    """
    Konvertiert eine GSM-Datei ins XML-Format.
    
    Args:
        gsmfile: Pfad zur GSM-Datei
    """
    filename = os.path.splitext(os.path.basename(gsmfile))[0]
    infolder = pjoin(C['projectpath'], FOLDER_GSM_WORK, filename)
    xmlfilename = pjoin(C['projectpath'], FOLDER_XML_LIBRARY, filename, filename+'.xml')
    sourcefolder = pjoin(C['projectpath'], FOLDER_SOURCE, filename)
    backupfolder = pjoin(C['projectpath'], FOLDER_XML_BACKUPS)
    
    # Backup erstellen, falls die XML-Datei existiert
    if not os.path.exists(backupfolder):
        os.makedirs(backupfolder)
    if os.path.exists(xmlfilename):
        shutil.copy(xmlfilename, pjoin(backupfolder, filename+datetime.datetime.now().strftime('_%Y_%m_%d_%H_%M')+'.xml'))
    
    # GSM-Datei kopieren
    if not os.path.exists(infolder):
        os.makedirs(infolder)
    shutil.copy(gsmfile, infolder)
    
    # Konvertierung durchführen
    lpxmlconverter('l2x', filename,
            '-img', pjoin(C['projectpath'], FOLDER_BITMAPS, filename),
            pjoin(C['projectpath'], FOLDER_GSM_WORK, filename),
            pjoin(C['projectpath'], FOLDER_XML_LIBRARY, filename))
    
    # Quellcodedateien extrahieren
    if not os.path.exists(sourcefolder):
        os.makedirs(sourcefolder)
    write_source(xmlfilename, sourcefolder)
    git_commit_source(C['projectpath'], 'g2x', filename)


def xml2gsm(gsmfile):
    """
    Konvertiert Quellcode-Dateien und XML in eine GSM-Datei.
    
    Args:
        gsmfile: Pfad zur Ziel-GSM-Datei
    """
    start = datetime.datetime.now()
    filename = os.path.splitext(os.path.basename(gsmfile))[0]
    file2backup = pjoin(C['projectpath'], FOLDER_GSM_WORK, filename, filename+'.gsm')
    xmlfilename = pjoin(C['projectpath'], FOLDER_XML_LIBRARY, filename, filename+'.xml')
    sourcefolder = pjoin(C['projectpath'], FOLDER_SOURCE, filename)
    outfolder = pjoin(C['projectpath'], FOLDER_XML_OUT)
    
    # Backup der bestehenden GSM-Datei erstellen
    if os.path.exists(file2backup):
        gsm_backups(file2backup, filename)
    
    # XML mit Quelldaten aktualisieren
    newxml = replace_with_source(xmlfilename, sourcefolder)
    if PRINT_TIMES: print('Prepare XML:', format_timedelta(datetime.datetime.now()-start))
    
    # Ausgabeordner bereinigen
    start = datetime.datetime.now()
    if os.path.exists(outfolder):
        for f in glob.glob(pjoin(outfolder, '*')):
            os.remove(f)
    else:
        os.makedirs(outfolder)
    if PRINT_TIMES: print('Clean outfolder:', format_timedelta(datetime.datetime.now()-start))
    
    # Aktualisierte XML-Datei schreiben
    start = datetime.datetime.now()
    xml_out_path = pjoin(C['projectpath'], FOLDER_XML_OUT, filename+'.xml')
    try:
        with open(xml_out_path, 'w', encoding='utf-8') as f:
            f.write(newxml)
        if PRINT_TIMES:
            time_str = format_timedelta(datetime.datetime.now()-start)
            print('Write XML:', time_str)
            if logger:
                logger.debug(f'Write XML: {time_str}')
    except Exception as e:
        error_msg = f'Error writing XML: {str(e)}'
        if logger:
            logger.error(error_msg)
        print(error_msg)
    
    # Temporäre Kopie der GSM-Datei erstellen
    start = datetime.datetime.now()
    temp_gsmfile = gsmfile+'.temp'
    shutil.copyfile(gsmfile, temp_gsmfile)
    if PRINT_TIMES: print('Make GSM temp copy:', format_timedelta(datetime.datetime.now()-start))
    
    # Konvertierung durchführen und bei Erfolg temporäre Datei entfernen
    if 0==lpxmlconverter('x2l', filename,
            '-img', pjoin(C['projectpath'], FOLDER_BITMAPS, filename),
            outfolder,
            os.path.dirname(gsmfile)):
        os.remove(temp_gsmfile)
        git_commit_source(C['projectpath'], 'x2g', filename)
    else:
        # Bei Fehler die ursprüngliche Datei wiederherstellen
        shutil.move(temp_gsmfile, gsmfile)
        print('Execute failed!')


def paramcsv(gsmfile):
    """
    Erstellt eine CSV-Datei mit Parameterbeschreibungen aus einer GSM-Datei.
    
    Args:
        gsmfile: Pfad zur GSM-Datei
    """
    filename = os.path.splitext(os.path.basename(gsmfile))[0]
    xmlfilename = pjoin(C['projectpath'], FOLDER_XML_LIBRARY, filename, filename+'.xml')
    tree = ET.ElementTree()
    
    # XML-Datei parsen
    try:
        tree.parse(xmlfilename)
    except Exception as e:
        print('Error trying to read', xmlfilename+'!', str(e))
        return
    
    # CSV-Datei erstellen
    csv_folder = pjoin(C['projectpath'], FOLDER_DOCUMENTATION)
    if not os.path.exists(csv_folder):
        os.makedirs(csv_folder)
        
    csvfilename = pjoin(csv_folder, filename+'.csv')
    try:
        f = open(csvfilename, 'w', encoding='utf-8-sig', newline='')
        csvwriter = csv.writer(f, dialect=csv.excel)
    except Exception as e:
        error_msg = f'Error creating CSV file: {str(e)}'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        return
    
    # Parameter auslesen und in CSV schreiben
    for paramNode in tree.findall('.//Parameters/*'):
        tag = paramNode.tag
        name = paramNode.attrib['Name']
        descNode = paramNode.find('./Description')
        valueNode = paramNode.find('./Value')
        
        # Wert extrahieren
        if valueNode is not None:
            value = [valueNode.text]
        else:
            value = []
            arrvaluesNode = paramNode.find('./ArrayValues')
            if arrvaluesNode is None:
                value = ['-']
            else:
                avalNodes = arrvaluesNode.findall('./AVal')
                for avalNode in avalNodes:
                    if 'Column' in avalNode.attrib:
                        value.append('ar[%s][%s]=%s' % (avalNode.attrib['Row'], avalNode.attrib['Column'], avalNode.text))
                    else:
                        value.append('ar[%s]=%s' % (avalNode.attrib['Row'], avalNode.text))
        
        # Flags extrahieren
        flagsNode = paramNode.find('Flags')
        for parflg in ['Child', 'BoldName', 'Unique', 'Hidden']:
            if flagsNode is not None:
                parflgNode = flagsNode.find('ParFlg_'+parflg)
                if parflgNode is not None:
                    value.append('1')
                else:
                    value.append('0')
            else:
                value.append('0')
                
        # Fix-Flag prüfen
        fixNode = paramNode.find('Fix')
        if fixNode is not None:
            value.append('1')
        else:
            value.append('0')
            
        # Zeile in CSV schreiben
        csvwriter.writerow([name, descNode.text.strip('"')]+value)
    
    f.close()
    if logger:
        logger.info(f'CSV written to: {csvfilename}')
    print('Written to:', csvfilename)


def paramcsv2(gsmfile):
    """
    Erstellt eine alternative CSV-Datei (XLS-Format) mit Parameterbeschreibungen aus einer GSM-Datei.
    
    Args:
        gsmfile: Pfad zur GSM-Datei
    """
    filename = os.path.splitext(os.path.basename(gsmfile))[0]
    xmlfilename = pjoin(C['projectpath'], FOLDER_XML_LIBRARY, filename, filename+'.xml')
    tree = ET.ElementTree()
    
    # XML-Datei parsen
    try:
        tree.parse(xmlfilename)
    except Exception as e:
        print('Error trying to read', xmlfilename+'!', str(e))
        return
    
    # CSV-Datei erstellen (als XLS-Format)
    csv_folder = pjoin(C['projectpath'], FOLDER_DOCUMENTATION)
    if not os.path.exists(csv_folder):
        os.makedirs(csv_folder)
        
    csvfilename2 = pjoin(csv_folder, filename+'_ruko'+'.xls')
    try:
        f = open(csvfilename2, 'w', encoding='utf-8-sig', newline='')
        csvwriter = csv.writer(f, dialect=csv.excel)
    except Exception as e:
        error_msg = f'Error creating CSV file: {str(e)}'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        return
    
    # Parameter auslesen und in CSV schreiben
    i = 0
    for paramNode in tree.findall(".//Parameters/*"):
        i = i + 1
        tag = paramNode.tag
        name = paramNode.attrib['Name']
        descNode = paramNode.find("./Description")
        valueNode = paramNode.find("./Flags")
        
        # BoldName-Flag prüfen
        value = ['?']
        if valueNode is not None:
            value = ['nein']
            mynode = valueNode.find("./ParFlg_BoldName")
            if mynode is not None:
                value = ['ja']
                
        # Laufende Nummer formatieren
        lfdnr = "%03d" % i
        
        # Zeile in CSV schreiben
        csvwriter.writerow([lfdnr, name, descNode.text.strip('"'), '1', '1-Spalte', '1', 'Ja']+value)
    
    f.close()
    if logger:
        logger.info(f'CSV written to: {csvfilename2}')
    print('Written to:', csvfilename2)


def parse_pict_xml(filename, sourcefilename, tagname):
    """
    Parst XML-Bild-Informationen aus einer Quelldatei.
    
    Args:
        filename: Dateiname ohne Erweiterung
        sourcefilename: Name der Quelldatei
        tagname: XML-Tag für Bildeinträge
        
    Returns:
        Dictionary mit Bild-Metadaten
        
    Raises:
        SystemExit: Bei XML-Parsing-Fehlern
    """
    sourcefolder = pjoin(C['projectpath'], FOLDER_SOURCE, filename)
    
    # Sicherstellen, dass der Quellordner existiert
    if not os.path.exists(sourcefolder):
        os.makedirs(sourcefolder)
        # Wenn die Datei nicht existiert, geben wir ein leeres Dictionary zurück
        if not os.path.exists(pjoin(sourcefolder, sourcefilename)):
            return {}
    
    # Quelldatei lesen
    try:
        with open(pjoin(sourcefolder, sourcefilename), 'r', encoding='utf-8') as f:
            rawxml = f.read()
    except Exception as e:
        error_msg = f'Error trying to read {sourcefilename}! {str(e)}'
        if logger:
            logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
        
    # Leere XML behandeln
    if not rawxml.strip():
        return {}
        
    sourcexml = '<root>'+rawxml+'</root>'  
    
    # XML parsen
    try:
        sourceroot = parseString(sourcexml)
    except ExpatError as e:
        error_msg = f'XML in {sourcefilename} could not be parsed! {ErrorString(e.code)}'
        if logger:
            logger.error(error_msg)
            lines = rawxml.splitlines()
            for lineno in range(e.lineno-4, e.lineno+3):
                if lineno>=0 and lineno<len(lines):
                    if lineno==e.lineno-1:
                        logger.error(f'* {lineno} {lines[lineno]}')
                    else:
                        logger.debug(f'  {lineno} {lines[lineno]}')
        print(error_msg)
        lines = rawxml.splitlines()
        for lineno in range(e.lineno-4, e.lineno+3):
            if lineno>=0 and lineno<len(lines):
                if lineno==e.lineno-1:
                    print('*', lineno, lines[lineno])
                else:
                    print(' ', lineno, lines[lineno])
        sys.exit(1)
    
    # Bildeinträge extrahieren
    files = {}
    for tag in sourceroot.getElementsByTagName(tagname):
        xmlfile = {}
        for (k, v) in list(tag.attributes.items()):
            xmlfile[k] = v
        files[xmlfile['path']] = xmlfile
        
    return files


def update_picture_xml(gsmfile):
    """
    Aktualisiert die Bildinformationen in XML-Dateien basierend auf 
    im Bitmap-Ordner vorhandenen Dateien.
    
    Args:
        gsmfile: Pfad zur GSM-Datei
    """
    filename = os.path.splitext(os.path.basename(gsmfile))[0]
    sourcefolder = pjoin(C['projectpath'], FOLDER_SOURCE, filename)
    bitmapfolder = pjoin(C['projectpath'], FOLDER_BITMAPS, filename)
    
    # Sicherstellen, dass der Quellordner existiert
    if not os.path.exists(sourcefolder):
        os.makedirs(sourcefolder)
        
    # Vorhandene Bilddateien finden
    if os.path.exists(bitmapfolder):
        existingfiles = glob.glob(pjoin(bitmapfolder, '*/*.*'))
    else:
        existingfiles = []
    
    # XML-Bildinformationen parsen
    xmlfiles = {'Picture': {}, 'GDLPict': {}}
    for sourcefilename, xmltag in XMLTAG_SOURCEXML.items():
        if xmltag in ['Picture', 'GDLPict']:
            source_path = pjoin(sourcefolder, sourcefilename)
            if os.path.exists(source_path):
                xmlfiles[xmltag] = parse_pict_xml(filename, sourcefilename, xmltag)
    
    # Höchste vorhandene SubIdent finden
    maxSubIdent = 0
    for xmltag in ['Picture', 'GDLPict']:
        for path, attributes in xmlfiles[xmltag].items():
            if 'SubIdent' in attributes and int(attributes['SubIdent']) > maxSubIdent:
                maxSubIdent = int(attributes['SubIdent'])
    
    # Vorhandene Dateien mit XML-Informationen abgleichen
    for existingfile in existingfiles:
        inxml = False
        for xmltag in ['Picture', 'GDLPict']:
            for path in list(xmlfiles[xmltag].keys()):
                if existingfile.endswith(path):
                    inxml = True
                    xmlfiles[xmltag][path]['exists'] = True
                    break
        
        # Neue Dateien hinzufügen
        if not inxml:
            path = existingfile.replace(bitmapfolder, '').strip('/')
            if path.startswith('\\') or path.startswith('/'):
                path = path[1:]
            maxSubIdent += 1
            mime = MimeTypes().guess_type(existingfile)[0]
            if mime is not None and mime.startswith('image/'):
                xmlfiles['GDLPict'][path] = {
                    'MIME': mime, 
                    'SectVersion': '19', 
                    'SectionFlags': '0', 
                    'SubIdent': str(maxSubIdent), 
                    'path': path, 
                    'exists': True
                }
    
    # Neues XML erstellen
    newxml = {}
    for xmltag in ['GDLPict']:
        for path, attributes in xmlfiles[xmltag].items():
            if 'exists' in attributes:
                newxml[int(attributes['SubIdent'])] = '<GDLPict MIME="%s" SectVersion="%s" SectionFlags="%s" SubIdent="%s" path="%s">\n</GDLPict>\n' \
                  % (attributes['MIME'], attributes['SectVersion'], attributes['SectionFlags'], 
                     attributes['SubIdent'], attributes['path'])
    
    # Sortiertes XML erstellen
    xml = ''
    for k in sorted(newxml.keys()):
        xml += newxml[k]
    
    # XML in Quelldateien schreiben
    for sourcefilename, xmltag in XMLTAG_SOURCEXML.items():
        if xmltag in ['GDLPict']:
            try:
                with open(pjoin(sourcefolder, sourcefilename), 'w', encoding='utf-8') as f:
                    f.write(xml)
                if logger:
                    logger.debug(f'Updated {sourcefilename}')
            except Exception as e:
                error_msg = f'Error writing {sourcefilename}: {str(e)}'
                if logger:
                    logger.error(error_msg)
                print(error_msg)


if __name__=='__main__':
    """
    Hauptprogramm - Verarbeitet Befehlszeilenargumente und führt die entsprechenden Aktionen aus.
    """
    if PRINT_TIMES: print('parameters', sys.argv[1:])
    
    # Parameter prüfen
    if len(sys.argv)<4:
        print('not enough parameters! gdlconverter.py mode foldername projectpath')
        sys.exit(1)
        
    mode = sys.argv[1]
    foldername = sys.argv[2]
    projectpath = sys.argv[3]
    
    # Logging initialisieren (muss früh erfolgen)
    setup_logging(projectpath)
    if logger:
        logger.info(f'Starting gdlconverter.py with mode: {mode}, folder: {foldername}')
    
    # Konfiguration laden
    config_path = pjoin(projectpath, 'gdlconfig.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            C = json.loads(f.read())
        if logger:
            logger.debug(f'Configuration loaded from {config_path}')
    except FileNotFoundError:
        error_msg = f"Error: Configuration file {config_path} not found"
        if logger:
            logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing JSON configuration: {str(e)}"
        if logger:
            logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
        
    C['projectpath'] = projectpath
    
    # Bibliotheksname automatisch aus dem ersten Ordnernamen unter 01_gsms/ ermitteln
    detected_name = detect_library_name(projectpath)
    if not detected_name:
        error_msg = f"Error: No library folder found in {pjoin(projectpath, FOLDER_GSM_BASE)}"
        if logger:
            logger.error(error_msg)
        print(error_msg)
        sys.exit(1)
    
    GSM_LIBRARY_NAME = detected_name
    
    if logger:
        logger.info(f'Detected library name: {GSM_LIBRARY_NAME}')
    
    # Globale Pfade initialisieren
    FOLDER_GSM_SOURCE = f'{FOLDER_GSM_BASE}/{GSM_LIBRARY_NAME}'
    # Auch Demo-Ordner berücksichtigen
    FOLDERS_GSMS = [
        FOLDER_GSM_SOURCE, 
        f'{FOLDER_GSM_SOURCE}/Makros',
        f'{FOLDER_GSM_BASE}/{GSM_LIBRARY_NAME}-Demo',
        f'{FOLDER_GSM_BASE}/{GSM_LIBRARY_NAME}-Demo/Makros'
    ]
    project_path = projectpath
    
    # LCF-Pfade initialisieren - Dateiname entspricht dem Bibliotheksnamen
    if 'lcf' in C and 'targetDirectory' in C['lcf']:
        lcf_dir = C['lcf']['targetDirectory']
    else:
        lcf_dir = '15_LCF'
    
    # LCF-Dateiname ist immer der Bibliotheksname (nicht "gdlnucleus.lcf")
    lcf_filename = f'{GSM_LIBRARY_NAME}.lcf'
    
    ziel = pjoin(project_path, lcf_dir, lcf_filename)
    quelle = pjoin(project_path, FOLDER_GSM_WORK)
    
    if logger:
        logger.debug(f'LCF target: {ziel}')
        logger.debug(f'LCF source: {quelle}')
    
    # Debug-Ausgabe konfigurieren
    if 'printtimes' not in C or not C['printtimes']:
        PRINT_TIMES = 0
    
    # LCF-Konvertierung direkt ausführen, wenn der Modus g2L ist
    if mode == 'g2L':
        if logger:
            logger.info(f"Converting GSM library to LCF: {quelle} -> {ziel}")
        print(f"Converting GSM library to LCF: {quelle} -> {ziel}")
        exitcode = convert_to_lcf()
        if logger:
            if exitcode == 0:
                logger.info(f"LCF conversion successful: {ziel}")
            else:
                logger.error(f"LCF conversion failed with exit code: {exitcode}")
        sys.exit(exitcode)
    # SVG zu TIFF Konvertierung
    if mode == 'svg2tiff':
        if logger:
            logger.info("Starting SVG to TIFF conversion")
        print("Starting SVG to TIFF conversion")
        exitcode = convert_svg_to_tiff()
        sys.exit(exitcode)    
    # Alle GSM-Dateien in den konfigurierten Ordnern verarbeiten
    for folder in FOLDERS_GSMS:
        folder_path = pjoin(projectpath, folder)
        if not os.path.exists(folder_path):
            continue
            
        gsmfiles = glob.glob(pjoin(folder_path, '*.gsm'))
        for gsmfile in gsmfiles:
            filename = os.path.splitext(os.path.basename(gsmfile))[0]
            if os.path.isfile(gsmfile):
                # foldername kann sein: "--all", Objektname, voller Pfad zu .gdl/.gsm, oder Verzeichnispfad
                if os.path.isfile(foldername):
                    _target = os.path.basename(os.path.dirname(foldername))
                else:
                    _target = os.path.basename(foldername)
                if foldername=='--all' or _target==filename:
                    if logger:
                        logger.info(f'Processing file: {gsmfile}')
                    print('File:', gsmfile)
                    
                    try:
                        # Entsprechende Aktion ausführen
                        if mode=='paramcsv':
                            paramcsv(gsmfile)
                        elif mode=='paramcsv2':
                            paramcsv2(gsmfile)
                        elif mode=='images':
                            update_picture_xml(gsmfile)
                        elif mode=='g2x':
                            gsm2xml(gsmfile)
                        elif mode=='l2hsf':
                            gsm2hsf(gsmfile)
                        elif mode=='h2g':
                            hsf2gsm(gsmfile)
                        else:
                            xml2gsm(gsmfile)
                        if logger:
                            logger.info(f'Successfully processed: {gsmfile}')
                    except Exception as e:
                        error_msg = f'Error processing {gsmfile}: {str(e)}'
                        if logger:
                            logger.error(error_msg, exc_info=True)
                        print(error_msg)
                        # Bei Batch-Verarbeitung weiter machen, bei Einzeldatei beenden
                        if foldername != '--all':
                            sys.exit(1)
