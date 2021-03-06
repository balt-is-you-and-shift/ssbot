import math
import os
import time
import json
import struct
import traceback
import easing_functions
from pathlib import Path
import zipfile

try:
	import mouse, keyboard
except ModuleNotFoundError:
	print('Mouse and keyboard modules not found. Did you forget to [pip install -r requirements.txt]?')
	exit(1)
except ImportError:
	print('Sorry, you have to be on root to use this on Linux due to a limitation with the keyboard and mouse modules.')
	exit(1)

def load_sspm(file):
	'''
	Load the notes from a .sspm. Pass in a file object.
	'''
	assert file.read(4) == b'SS+m', 'Invalid header! Did you select a .sspm?' # Header
	version = int.from_bytes(file.read(2),'little')
	if version == 1:
		assert int.from_bytes(file.read(2),'little') == 0, 'Reserved bytes were not 0! Did you try to load a modchart?'
		while file.read(1) != b'\x0A': pass #id
		while file.read(1) != b'\x0A': pass #name
		while file.read(1) != b'\x0A': pass #creator
		file.seek(4,1) #ms length
		file.seek(4,1) #note count
		file.seek(1,1) #difficulty + 1
		match int.from_bytes(file.read(1),'little'): #is there a cover
			case 1:
				file.read(2) #im width
				file.read(2) #im height
				file.read(1) #mip (huh?)
				file.read(1) #format
				clen = file.read(8) #content length
				file.read(int.from_bytes(clen,'little'))
			case 2:
				clen = file.read(8) #content length
				file.read(int.from_bytes(clen,'little'))
		file.read(1) #music storage type
		clen = file.read(8) #content length
		file.read(int.from_bytes(clen,'little')) #music data
		notes = []
		while len(timing_raw := file.read(4)): #for the rest of the file
			timing = int.from_bytes(timing_raw,'little') #timing
			if int.from_bytes(file.read(1),'little'): #if it's a quantum note
				x,y = struct.unpack('f',file.read(4))[0],struct.unpack('f',file.read(4))[0] #float coords
			else:
				x,y = int.from_bytes(file.read(1),'little'),int.from_bytes(file.read(1),'little') #int coords
			notes.append([2-x,2-y,timing])
		return notes[1:] #for some reason there's a weird note that doesn't actually exist in-game, so i clip it off here
	#elif version == 2: ...
	else:
		raise AssertionError('Unsupported map version!')

def paginated_picker(dictionary: dict, message: str, items: int = 10):
	page = 0
	dkeys = list(dictionary.keys())
	dkeys.sort()
	while True:
		print(f'\x1b[H\x1b[2J\x1b[3J{message}')
		for i, key in enumerate(dkeys[page*items:(1+page)*items]):
			print(f'[{i}] {key}')
		print(f'\nPage {page}/{len(dictionary)//items}\n[.] Next page\n[,] Previous page\n[j###] Jump to page')
		i = input('> ')
		try:
			return (dkeys[(page*items)+int(i)],dictionary[dkeys[(page*items)+int(i)]])
		except ValueError: pass
		if i == ',':
			page = (page-1)%(math.ceil(len(dictionary)/items))
		elif i == '.':
			page = (page+1)%(math.ceil(len(dictionary)/items))
		elif i.startswith('j'):
			try:
				page = int(i[1:])%(math.ceil(len(dictionary)/items))
			except:
				pass
		

def main():
	print('''\x1b[H\x1b[2J\x1b[3JStarting SSBot. Don't use this to fake a score, you won't get away with it.''')
	if Path('./config.json').exists():
		try:
			with open('./config.json','r') as config_file:
				config = json.load(config_file)
			i = input('Would you like to reset config?\n[Y] for yes, [Not Y] for no\n')
			do_config = i.lower() == 'y'
		except KeyboardInterrupt:
			raise #catch KeyboardInterrupt correctly here
		except:
			print('Config file invalid, resetting config...')
			do_config = True
	else:
		print('''Config file not found. Assuming this is your first time using SSBot:
1: In SS+, go to Settings > Camera & Control.
2: Set your sensitivity to 1.
3: Uncheck "Lock Mouse".''')
		do_config = True
	if do_config:
		config = {}
		easings = {k:v for k,v in easing_functions.__dict__.items() if (not k.startswith('__')) and (k != 'easing')}
		easing_name, easing = paginated_picker(easings,"Pick an easing function to use:",5)
		easing = easing(start=0,end=1)
		with open('./config.json','w+') as config_file:
			config['easing'] = easing_name
			json.dump(config,config_file)
	else:
		easing = easing_functions.__dict__[config['easing']](start=0,end=1)
	def move_to(x,y,center):
		x, y = ((1-x)*55.3333333333)+center[0], ((1-y)*55.3333333333)+center[1]
		mouse.move(x,y)
	while True:
		try:
			i = input('\x1b[H\x1b[2J\x1b[3JInput a song with:\n[1] Raw data [paste in]\n[2] Raw data [.txt]\n[3] SS+ map file [.sspm]\n[4] SS+ map pack [.sspmr] (Legacy)\n[5] Vulnus map [.zip]\n')
			if i == '1':
				for note in input('Input song data: ').split(',')[1:]:
					try:
						song_raw.append([float(n) for n in note.split('|')])
					except ValueError:
						pass
			else:
				if len(i):
					while (not Path(f_path := input('Input file path: ')).exists()): pass
				match i:
					case '2':
						with open(f_path,'r') as f:
							song_raw = []
							for note in f.read().split(',')[1:]:
								try:
									song_raw.append([float(n) for n in note.split('|')])
								except ValueError:
									pass
						break
					case '3':
						try:
							with open(f_path,'rb') as f:
								song_raw = load_sspm(f)
						except AssertionError as e:
							print(f'There\'s a problem with this map.\n{e.args[0]}')
							input('Press enter to import a different map...')
							continue
					case '4':
						songs = {}
						with open(f_path,'r') as f:
							for line in f.readlines():
								if line.startswith('#'):
									pass
								else:
									s = line.split(':~:')
									songs[s[2]] = s[-1] #name: data
						name, song_data = paginated_picker(songs,"Pick a song to play:",10)
						song_raw = []
						for note in song_data.split(',')[1:]:
							try:
								song_raw.append([float(n) for n in note.split('|')])
							except ValueError:
								pass
					case '5':
						with open(f_path,'rb') as f:
							v_song = zipfile.ZipFile(f)
							with v_song.open('meta.json') as meta:
								meta = json.load(meta)
							with v_song.open(meta['_difficulties'][0]) as map_data:
								map_data = json.load(map_data)
							song_raw = []
							for note in (notes := map_data['_notes']):
								song_raw.append([1-note['_x'],note['_y']+1,int(note['_time']*1000)])
					case _:
						print("\x1b[H\x1b[2J\x1b[3J", end="")
						continue
			break
		except KeyboardInterrupt:
			raise
		except AssertionError as e:
			print(f"\x1b[H\x1b[2J\x1b[3JAn assertion failed during import.\n{e.args[0]}")
			input('Press enter to import a different map...')
		except Exception as e:
			print(f"\x1b[H\x1b[2J\x1b[3JAn error occurred while importing the map:\n{e.__class__.__name__}: {e.args[0]}")
			input('Press enter to import a different map...')
	song = []
	notes = []
	avg = lambda args: sum(args)/len(args)
	for note in song_raw:
		if len(notes):
			if note[2]-notes[0][2] < 10:
				notes.append(note)
			else:
				song.append([avg([note[0] for note in notes]),avg([note[1] for note in notes]),notes[0][2]])
				notes = [note]
		else:
			notes.append(note)
	if len(notes):
		song.append([avg([note[0] for note in notes]),avg([note[1] for note in notes]),notes[0][2]])
	print('\x1b[H\x1b[2J\x1b[3JSong loaded, click play\nPress F7 when the first note is at the timing window to start')
	keyboard.wait(65) #wait for F7
	center = mouse.get_position()
	old_time = time.perf_counter()
	start_timing = song[0][2]
	offset = start_timing
	print(f'\rOffset set to {offset-start_timing}ms',end='                     ')
	move_to(*song[0][:2],center)
	old_note = song.pop(0)
	while len(song):
		note = song[0]
		try:
			t = (time.perf_counter()-(old_time + ((old_note[2]-offset)/1000)))/(((note[2]-offset)/1000)-((old_note[2]-offset)/1000))
			t = min(max(t,0),1) #clamp between 0 and 1
			delta = easing(t)
		except ZeroDivisionError:
			delta = 1
		move_to(*[(old*(1-delta))+(new*delta) for old, new in zip(old_note[:2],note[:2])],center)
		if t >= 1:
			old_note = song.pop(0)
		if keyboard.is_pressed(77):
			if kr:
				kr = False
				offset += 10 if keyboard.is_pressed('shift') else 1
				print(f'\rOffset set to {offset-start_timing}ms',end='                     ')
		else:
			kr = True
		if keyboard.is_pressed(75):
			if kl:
				kl = False
				offset -= 10 if keyboard.is_pressed('shift') else 1
				print(f'\rOffset set to {offset-start_timing}ms',end='                     ')
		else:
			kl = True
		if keyboard.is_pressed(57) or keyboard.is_pressed(1):
			print('\n[!] Song stopped prematurely.')
			break
	print('\nSong finished!')


if __name__ == "__main__":
	main()