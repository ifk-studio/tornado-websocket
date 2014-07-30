# -*- coding: utf-8 -*-

import os.path
import subprocess
import time


def compile_translations(locale_dir):
    """
    Checks if .mo compiled files exist, if not compiles from .po
    """

    def compile_po(ext, dirname, names):
        if 'default.po' in names:  # and 'default.mo' not in names:
            try:
                command = ["msgfmt",
                           "%s/default.po" % dirname,
                           "-o",
                           "%s/default.mo" % dirname]

                subprocess.call(command)
                print 'compiled .mo'
            except:
                pass

    extension = {'.po': '.mo'}
    os.path.walk(locale_dir, compile_po, extension)


def compile_translations_err(buffer):
    """
    Checks if .mo compiled files exist, if not compiles from .po
    """

    def compile_po(ext, dirname, names):
        ext.write(dirname)
        ext.write(str(os.listdir(dirname)))
        ext.write('  ')

        if 'default.po' in names:  #and 'default.mo' not in names:
            ext.write(str(os.path.isfile("%s/default.po" % dirname)))
            command = ["msgfmt",
                       "%s/default.po" % dirname,
                       "-o",
                       "%s/default.mo" % dirname]
            ext.write(str(subprocess.call(command)))
            ext.write(str(subprocess.call(['ls'])))
            ext.write(str(subprocess.call(['which', 'msgfmt'])))
            ext.write(str(subprocess.call(['which', 'msgfmt124'])))
            ext.write('  ')
            ext.write(str(os.listdir(dirname)))
            ext.write('  ')

    extension = buffer
    locale_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app/Locale'))
    os.path.walk(locale_dir, compile_po, extension)
