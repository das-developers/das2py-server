#!/usr/bin/env python

# Embed the config file location.  Code should be safe back to python 2.6.

import sys
import os
import re
import tokenize
from os.path import join as pjoin
from stat import ST_MODE

from distutils import log
from distutils import sysconfig
from distutils.core import setup
from distutils.dep_util import newer
from distutils.util import convert_path, change_root

from distutils.command.build		 import build
from distutils.command.build_scripts import build_scripts
from distutils.command.install_data  import install_data

from distutils.errors import DistutilsFileError


g_sPrefix = os.getenv('PREFIX')

if not g_sPrefix:
	sys.stderr.write('ERROR:  Environment var PREFIX is not defined\n')
	sys.exit(7)

g_sEtc	= pjoin(g_sPrefix, 'etc')
g_sConfig = pjoin(g_sEtc, 'das2server.conf')


##############################################################################
# Need a custom build_py to write the config file directory into any scripts

class build_scripts_wconf(build_scripts):
	r"""Custom build class that embeds the install location of the das2
	server config file in scripts that have BOTH a shebang and a 
	'g_sConfDir = Thing' line.
	"""
	
	def embed_config(self, lLines, encoding):
		r"""Convert lines that start with g_sConfPath (no proceeding whitespace)
		and change them to g_sConfPath = $SERVER_ETC/das2server.conf
		"""
		
		# Not efficient, don't care, it's easy to read and this is just install
		# code.
		for i in range(0, len(lLines)):
			match = self.config_re.match(lLines[i])
			if not match: continue
	
			if sys.version_info.major > 2:  
				s = "g_sConfPath = '%s'\n"%g_sConfig
				lLines[i] = s.encode(encoding)
			
			else:
				lLines[i] = "g_sConfPath = '%s'\n"%g_sConfig
		
		return lLines
		
	
	def copy_scripts_2(self):
		"""Copy each script listed in 'self.scripts'; if it's marked as a
		Python script in the Unix way (first line matches 'first_line_re',
		ie. starts with "\#!" and contains "python"), then adjust the first
		line to refer to the current Python interpreter as we copy.
		"""
		_sysconfig = __import__('sysconfig')
		self.mkpath(self.build_dir)
		outfiles = []
		for script in self.scripts:
			adjust = 0
			script = convert_path(script)
			outfile = os.path.join(self.build_dir, os.path.basename(script))
			outfiles.append(outfile)

			if not self.force and not newer(script, outfile):
				log.debug("not copying %s (up-to-date)", script)
				continue

			# Always open the file, but ignore failures in dry-run mode --
			# that way, we'll get accurate feedback if we can read the
			# script.
			try:
				f = open(script, "r")
			except IOError:
				if not self.dry_run:
					raise
				f = None
			else:
				first_line = f.readline()
				if not first_line:
					self.warn("%s is an empty file (skipping)" % script)
					continue

				match = self.first_line_re.match(first_line)
				if match:
					adjust = 1
					post_interp = match.group(1) or ''

			if adjust:
				log.info("copying and adjusting %s -> %s", script,
						 self.build_dir)
				if not self.dry_run:
					outf = open(outfile, "w")
					if not _sysconfig.is_python_build():
						outf.write("#!%s%s\n" %
								   (self.executable,
									post_interp))
					else:
						outf.write("#!%s%s\n" %
								   (os.path.join(
							_sysconfig.get_config_var("BINDIR"),
						   "python%s%s" % (_sysconfig.get_config_var("VERSION"),
										   _sysconfig.get_config_var("EXE"))),
									post_interp))
					outf.writelines(self.embed_config(f.readlines(), None))
					outf.close()
				if f:
					f.close()
			else:
				if f:
					f.close()
				self.copy_file(script, outfile)

		if os.name == 'posix':
			for file in outfiles:
				if self.dry_run:
					log.info("changing mode of %s", file)
				else:
					oldmode = os.stat(file)[ST_MODE] & 0o7777
					newmode = (oldmode | 0o555) & 0o7777
					if newmode != oldmode:
						log.info("changing mode of %s from %o to %o",
								 file, oldmode, newmode)
						os.chmod(file, newmode)
						
		# copy_scripts_2()
	
	
	def copy_scripts_3(self):
		r"""Copy each script listed in 'self.scripts'; if it's marked as a
		Python script in the Unix way (first line matches 'first_line_re',
		ie. starts with "\#!" and contains "python"), then adjust the first
		line to refer to the current Python interpreter as we copy.
		"""
		self.mkpath(self.build_dir)
		outfiles = []
		updated_files = []
		for script in self.scripts:
			adjust_shebang = False
			adjust_config  = False
			script = convert_path(script)
			outfile = os.path.join(self.build_dir, os.path.basename(script))
			outfiles.append(outfile)

			if not self.force and not newer(script, outfile):
				log.debug("not copying %s (up-to-date)", script)
				continue

			# Always open the file, but ignore failures in dry-run mode --
			# that way, we'll get accurate feedback if we can read the
			# script.
			try:
				f = open(script, "rb")
			except OSError:
				if not self.dry_run:
					raise
				f = None
			else:
				encoding, lines = tokenize.detect_encoding(f.readline)
				f.seek(0)
				first_line = f.readline()
				if not first_line:
					self.warn("%s is an empty file (skipping)" % script)
					continue

				match = self.first_line_re.match(first_line)
				if match:
					adjust_shebang = True
					post_interp = match.group(1) or b''

			if adjust_shebang:
				log.info("copying and adjusting %s -> %s", script,
						 self.build_dir)
				updated_files.append(outfile)
				if not self.dry_run:
					if not sysconfig.python_build:
						executable = self.executable
					else:
						executable = os.path.join(
							sysconfig.get_config_var("BINDIR"),
						   "python%s%s" % (sysconfig.get_config_var("VERSION"),
										   sysconfig.get_config_var("EXE")))
					executable = os.fsencode(executable)
					shebang = b"#!" + executable + post_interp + b"\n"
					# Python parser starts to read a script using UTF-8 until
					# it gets a #coding:xxx cookie. The shebang has to be the
					# first line of a file, the #coding:xxx cookie cannot be
					# written before. So the shebang has to be decodable from
					# UTF-8.
					try:
						shebang.decode('utf-8')
					except UnicodeDecodeError:
						raise ValueError(
							"The shebang ({!r}) is not decodable "
							"from utf-8".format(shebang))
					# If the script is encoded to a custom encoding (use a
					# #coding:xxx cookie), the shebang has to be decodable from
					# the script encoding too.
					try:
						shebang.decode(encoding)
					except UnicodeDecodeError:
						raise ValueError(
							"The shebang ({!r}) is not decodable "
							"from the script encoding ({})"
							.format(shebang, encoding))
					with open(outfile, "wb") as outf:
						outf.write(shebang)
						outf.writelines(self.embed_config(f.readlines(), encoding))
				if f:
					f.close()
			else:
				if f:
					f.close()
				updated_files.append(outfile)
				self.copy_file(script, outfile)

		if os.name == 'posix':
			for file in outfiles:
				if self.dry_run:
					log.info("changing mode of %s", file)
				else:
					oldmode = os.stat(file)[ST_MODE] & 0o7777
					newmode = (oldmode | 0o555) & 0o7777
					if newmode != oldmode:
						log.info("changing mode of %s from %o to %o",
								 file, oldmode, newmode)
						os.chmod(file, newmode)
		# XXX should we modify self.outfiles?
		return outfiles, updated_files

	def copy_scripts (self):
		
		if sys.version_info.major > 2:
			self.config_re = re.compile(b'^g_sConfPath\s+=\s+.*$')
			self.first_line_re = re.compile(b'^#!.*python[0-9.]*([ \t].*)?$')
			self.copy_scripts_3()
			
		else:
			# Attempt to get python 2.6 by not including b prefix in non 3 code
			self.config_re = re.compile('^g_sConfPath\s+=\s+.*$')
			self.first_line_re = re.compile('^#!.*python[0-9.]*([ \t].*)?$')
			self.copy_scripts_2()


##############################################################################

# Global hack to deal with lack of access to command constructor
g_lKeepDest = []

class install_data_wconf(install_data):
	"""Copies data files any files that have the extension *.in are 
	treated as a python format string and a dictionary consisting of the
	current environment plus the 
	"""
	
	def __init__(self, dist):
		install_data.__init__(self,dist)
		self.lKeepDest = g_lKeepDest
	
	def file_from_tplt(self, src, dst, verbose=1, dry_run=0):
		"""Replicate some of the dist_utils copy file code here"""
	
		if not os.path.isfile(src):
			raise DistutilsFileError(
				"can't copy '%s': doesn't exist or not a regular file" % src
			)
		
		if os.path.isdir(dst):
			dir = dst
			if not src.endswith('.in'):
				raise ValueError("input file %s doesn't end with '.in'"%src)
			src_strip = src[:-3]  # Strip the .in from the end of the file
			dst = os.path.join(dst, os.path.basename(src_strip))
		else:
			dir = os.path.dirname(dst)
			
		# If the destination exists and is in our "don't overwrite" list
		# ignore the install
		if os.path.isfile(dst) and (os.path.basename(dst) in self.lKeepDest):
			return (dst, 0)
		

		if verbose >= 1:
			if os.path.basename(dst) == os.path.basename(src):
				log.info("generating from template: %s -> %s", src, dir)
			else:
				log.info("generating from template: %s -> %s", src, dst)

		if dry_run:
			return (dst, 1)
		
		fIn = open(src, 'r')
		sFmt = fIn.read()
		fIn.close()
			
		# Substitute environment variables
		sDat = sFmt%os.environ
		
		fOut = open(dst, 'wb')
		fOut.write(sDat.encode(encoding='utf-8'))
		fOut.close()
		
		# if dst ends in any recognizable shell script patterns, make it
		# executable
		sufficies = ('.sh','.ksh','.py')
		for suffix in sufficies:
			if dst.endswith(suffix): 
				log.info("changing mode of %s to 755"%dst)
				os.chmod(dst, 0o755)
		
		return (dst, 1)
	
	
	def copy_file_or_tplt(self, sFile, sDir):
		if not sFile.endswith('.in'):
			
			if os.path.isdir(sDir):
				sFinal = os.path.join(sDir, os.path.basename(sFile))
			else:
				sFinal = sDir
			
			# If the destination exists and is in our "don't overwrite" list
			# ignore the install.  This is different from the perserve_mode=1
			# behavior for copy_file in that it doesn't care about file times.
			if os.path.isfile(sFinal) and (os.path.basename(sFinal) in self.lKeepDest):
				return (sFinal, 0)
			else:
				return self.copy_file(sFile, sDir)
				
		else:
			return self.file_from_tplt(sFile, sDir)			
	
	
	def run(self):
	
		self.mkpath(self.install_dir)
		for f in self.data_files:
			if isinstance(f, str):
				# it's a simple file, so copy it
				f = convert_path(f)
				if self.warn_dir:
					self.warn("setup script did not provide a directory for "
							  "'%s' -- installing right in '%s'" %
							  (f, self.install_dir))
				
				(out, _) = self.copy_file_or_tplt(f, self.install_dir)
				if out: self.outfiles.append(out)
				
			else:
				# it's a tuple with path to install to and a list of files
				dir = convert_path(f[0])
				if not os.path.isabs(dir):
					dir = os.path.join(self.install_dir, dir)
				elif self.root:
					dir = change_root(self.root, dir)
				self.mkpath(dir)

				if f[1] == []:
					# If there are no files listed, the user must be
					# trying to create an empty directory, so add the
					# directory to the list of output files.
					self.outfiles.append(dir)
				else:
					# Copy files, adding them to the list of output files.
					for data in f[1]:
					
						data = convert_path(data)
					
						(out, _) = self.copy_file_or_tplt(data, dir)
				
						if out: self.outfiles.append(out)
	

##############################################################################

lPkg = [
	'das2server','das2server.util','das2server.defhandlers', 
	'das2server.deftasks', 'das2server.h_api'
]

lScripts = [ 'scripts/%s'%s for s in [
	'das2_srv_arbiter', 'das2_srvcgi_logrdr', 'das2_srvcgi_main',
	'das2_srv_passwd',  'das2_srv_todo'
]]

lDataFiles = [
	('bin', ['scripts/das2_startup.sh.in']),
	('etc', [
		'etc/das2server.conf.example.in','etc/das2peers.ini.example.in',
		'etc/group', 'etc/passwd'
	]),
	
	# the resource files
	('static', [
		'static/das2logo.png',    'static/das2server.xsl', 
		'static/magnetosphere.jpg', 'static/das2logo_rv.png',
		'static/das2server.css', 'static/hapi_sm.png',
		'static/logo.png'
	]),
	
	# And a couple empty dirs...
	('log', []), ('cache', [])

]

# Hack in a "--no-examples" argument
if '--no-examples' in sys.argv:
	sys.argv.remove('--no-examples')
else:
	lDataFiles.append( 
		('datasets/Examples', [
			'examples/Random.dsdf.in', 'examples/Spectra.dsdf.in',
			'examples/Waveform.dsdf.in', 'examples/Params.dsdf.in',
			'examples/Auth.dsdf.in', 'examples/_dirinfo_.dsdf'
		])
	)
	lDataFiles.append( 
		('examples', [
			'examples/randata.py','examples/spectra.sh.in', 'examples/waveform.py',
			'examples/cdf.py'
		])
	)
	lDataFiles.append( 
		('examples/vgr_data', [
			'examples/vgr_data/VG1_1979-03-01_12-26-11-956.DAT',
			'examples/vgr_data/VG1_1979-03-01_12-26-59-956.DAT',
			'examples/vgr_data/VG1_1979-03-01_12-27-47-956.DAT',
			'examples/vgr_data/VG1_1979-03-01_12-28-35-956.DAT'
		])
	)
	lDataFiles.append( 
		('examples/themis_data', [
			'examples/themis_data/tha_l3_sm_20080629_171151_20080629_171152_burst_v01.cdf'
		])
	)


# Hack around command constructors not accessable.  These files won't be
# overwritten if destination exists.
g_lKeepDest = ['passwd', 'group']

setup(
   name="das2server",
	version="2.2",
	description="Das2 pyserver - a das2 stream caching and reduction CGI service",
	author="Chris Piker",
	packages=lPkg,
	scripts=lScripts,
	data_files=lDataFiles,
	cmdclass={
		'build_scripts':build_scripts_wconf,
		'install_data':install_data_wconf
		
	}
)
