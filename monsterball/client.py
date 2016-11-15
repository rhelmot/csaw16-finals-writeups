#!/usr/bin/env python

import ssl
import socket
import struct
import random

from collections import defaultdict

from request_pb2 import *   # pylint: disable=wildcard-import,unused-wildcard-import

import logging
l = logging.getLogger('monsters.client')
l.setLevel('DEBUG')

server = ('reversing.chal.csaw.io', 1348)

BALL = 0
SUPER_BALL = 1
UBER_BALL = 2
STANDARD_HEAL = 3
SUPER_HEAL = 4
KEG_OF_HEALTH = 5
MEGA_SEED = 6

class RawResponse(object):
  def __init__(self, s):
    self.string = s

  @staticmethod
  def FromString(data):
    return RawResponse(data)

  def SerializeToString(self):
    return self.string

  def __str__(self):
    return 'raw: %s\n' % repr(self.string)

RawRequest = RawResponse

class Client(object):
  def __init__(self, sock):
    self.sock = sock
    self.id = None
    self.connectionid = None

    self.player = None
    self.monsters = None
    self.captured = None
    self.treats = None
    self.inventory = {}

    self.map = defaultdict(dict)
    self.recent_stops = set()
    self.nearby_stops = []
    self.nearby_monsters = []

    self.log = []

  @staticmethod
  def connect(addr=server):
    s = socket.socket()
    s.connect(addr)

    ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    return Client(ctx.wrap_socket(s))

  def write_packet(self, s):
    out = 0
    s = struct.pack('H', len(s)) + s
    while out < len(s):
      out += self.sock.write(s[out:])

  def recv_exactly(self, n):
    out = ''
    while len(out) < n:
      out += self.sock.read(n - len(out))
    return out

  def read_packet(self, dataclass, header=4):
    length = self.recv_exactly(header)
    data = self.recv_exactly(struct.unpack('I' if header == 4 else 'H', length)[0])
    val = dataclass.FromString(data)
    return val

  def request(self, reqtype, data, responsetype):
    reqtype = Request.RequestType.Value(reqtype)
    if type(data) is not str:
      str_data = data.SerializeToString()
    else:
      str_data = data
    request = Request(type=reqtype, data=str_data)
    self.write_packet(request.SerializeToString())
    result = self.read_packet(responsetype)
    self.log.append((request, data, result))
    return result

  def login(self, username, password):
    result = self.request('Login', LoginRequest(username=username, password=password), LoginResponse)
    if result.status != 1:
      import ipdb; ipdb.set_trace()

    self.id = result.id
    self.connectionid = result.connectionid
    self.get_all_player_info()

  def register(self, username=None, password=None):
    if username is None:
      username = ''.join(random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in xrange(10))
    if password is None:
      password = ''.join(random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in xrange(10))

    l.warning("Registering with username '%s' and password '%s'", username, password)

    open('.creds', 'w').write('%s %s' % (username, password))

    result = self.request('Register', RegisterRequest(username=username, password=password), RegisterResponse)
    if result.status != 1:
      import ipdb; ipdb.set_trace()

    self.id = result.id
    self.connectionid = result.connectionid
    self.get_all_player_info()

  def get_all_player_info(self, refresh=False):
    result = self.request('GetAllPlayerInfo', '' if refresh else self.cr_token, GetAllPlayerInfoResponse)
    self.player = result.player
    self.monsters = result.monsters.monsters
    self.captured = result.captured.captured
    self.treats = {t.species: t.count for t in result.treats.treats}
    self.inventory = {i.item: i.count for i in result.inventory.items}
    l.info("You have %d balls", self.num_balls)
    l.info("You have captured %d/103 monsters", self.num_monsters_caught)
    l.info("You are level %d", self.player.level)

  @property
  def num_balls(self):
    return self.item_count(BALL) + self.item_count(SUPER_BALL) + self.item_count(UBER_BALL)

  def item_count(self, item):
    try:
      return self.inventory[item]
    except KeyError:
      return 0

  @property
  def cr_token(self):
    v1 = self.connectionid ^ 0xC0DECAFEFEEDFACE
    v2 = (25214903917 * v1) % 2**64
    v1 = (v1 >> 17) | ((v1 << (64 - 17)) % 2**64)
    return struct.pack('Q', (v2 + v1 + 11) % 2**64)

  @property
  def num_monsters_caught(self):
    return len(self.captured)

  def refresh_map(self):
    x = self.player.x
    y = self.player.y
    self.nearby_stops = []

    while x % 128 != 0: x -= 1
    while y % 128 != 0: y -= 1

    result = self.request('GetMapTiles', GetMapTilesRequest(x=x, y=y), GetMapTilesResponse)
    assert len(result.data) == 64*128
    for xi in xrange(0, 128, 2):
      for yi in xrange(128):
        tile = ord(result.data[xi/2 + yi*64])
        self.map[xi + x][yi + y] = tile & 0xf
        self.map[xi + x + 1][yi + y] = tile >> 4
        if tile & 0xf == 0xf:
          self.nearby_stops.append((xi + x, yi + y))
        if tile & 0xf0 == 0xf0:
          self.nearby_stops.append((xi + x + 1, yi + y))

  def render_map(self):
    x = self.player.x
    y = self.player.y
    print 'top:', x, y
    while x % 128 != 0: x -= 1
    while y % 128 != 0: y -= 1
    rangex = range(x, x+128)
    rangey = range(y, y+128)
    print '\n'.join(' '.join('%x'%self.map[x][y] if self.map[x][y] != 0 else ' ' for x in rangex) for y in rangey)

  def does_monster_exist(self, monster):
    for a in self.nearby_monsters:
      if a.x == monster.x and a.y == monster.y:
        return True
    return False

  def refresh_stops(self):
    result = self.request('GetRecentStops', '', GetRecentStopsResponse)
    self.recent_stops = set((s.x, s.y) for s in result.stops)

  def move(self, x, y):
    l.debug('Moving to %d,%d', x, y)
    MAX_MOTION = 8

    while self.player.x != x:
      dx = x - self.player.x
      inc = max(min(dx, MAX_MOTION), -MAX_MOTION)
      self.player.x += inc
      self.refresh_monsters()

    while self.player.y != y:
      dy = y - self.player.y
      inc = max(min(dy, MAX_MOTION), -MAX_MOTION)
      self.player.y += inc
      self.refresh_monsters()

  def refresh_monsters(self):
    result = self.request('GetMonstersInRange', GetMonstersInRangeRequest(x=self.player.x, y=self.player.y), GetMonstersInRangeResponse)
    self.nearby_monsters = result.sightings

  def stop_is_active(self, stop):
    return stop not in self.recent_stops

  def visit_stop(self, stop):
    self.move(stop[0], stop[1] + 1)
    result = self.request('GetItemsFromStop', GetItemsFromStopRequest(x=stop[0], y=stop[1]), GetItemsFromStopResponse)
    l.info("Got %d items from stop", sum(x.count for x in result.items))
    self.update_inventory()

  def update_inventory(self):
    result = self.request('GetInventory', '', GetInventoryResponse)
    self.inventory = {i.item: i.count for i in result.items}

  def uncaught_monster(self, monster):
    for caught in self.captured:
      if caught.species == monster.species:
        return False
    return True

  def catch(self, monster):
    x = monster.x
    y = monster.y
    self.move(x, y)
    if not self.does_monster_exist(monster):
      l.warning("Monster disappeared...")
      return False
    validation = (((91939 * y + 694847539 * x + 92893) % 2**64) >> 16) % 2**32
    encounter = self.request('StartEncounter', StartEncounterRequest(x=monster.x, y=monster.y, data=validation), StartEncounterResponse)
    l.info("Fighting monster %d (level %d)", encounter.species, encounter.level)

    while True:
      self.update_inventory()
      if self.item_count(UBER_BALL) > 0:
        ball = UBER_BALL
        l.debug("Throwing uber ball...")
      elif self.item_count(SUPER_BALL) > 0:
        ball = SUPER_BALL
        l.debug("Throwing super ball...")
      else:
        ball = BALL
        l.debug("Throwing ball...")
      throw = self.request('ThrowBall', ThrowBallRequest(ball=ball), ThrowBallResponse)
      if throw.result == 0:
        l.info("Caught!")
        return True
      elif throw.result >= 4 or throw.result <= 6:
        l.info("Escaped...")
        return False

  def default_login(self):
    try:
      username, password = open('.creds').read().split()
      self.login(username, password)
    except: # pylint: disable=bare-except
      self.register()

  def catch_em_all(self):
    self.default_login()
    self.refresh_monsters()

    center_x = self.player.x
    center_y = self.player.y
    direction = 1

    while self.num_monsters_caught < 103:
      self.refresh_map()
      self.refresh_stops()

      if abs(center_y) + 128 > 2048:
        direction = -direction
        center_x += 128
        self.move(center_x, center_y)
        self.refresh_map()
        self.refresh_stops()

      if self.num_balls < 300:
        for stop in self.nearby_stops:
          if self.stop_is_active(stop):
            self.visit_stop(stop)

      if self.num_balls != 0:
        self.refresh_monsters()
        while any(map(self.uncaught_monster, self.nearby_monsters)):
          for monster in self.nearby_monsters:
            if self.uncaught_monster(monster):
              if self.catch(monster):
                self.get_all_player_info(True)
              self.refresh_monsters()
              break

      center_y += 128 * direction
      self.move(center_x, center_y)

    print self.get_flag_1()

  def get_flag_1(self):
    result = self.request('GetCatchEmAllFlag', '', GetCatchEmAllFlagResponse)
    return result.flag

  def become_strong(self):
    self.default_login()
    self.refresh_monsters()

    center_x = self.player.x
    center_y = self.player.y
    direction = 1
    direction2 = 1
    while self.player.level < 40:
      self.refresh_map()
      self.refresh_stops()

      if abs(center_y) + 128 >= 2048:
        if abs(center_x) + 128 >= 2048:
          direction2 = -direction2

        direction = -direction
        center_x += 128 * direction2
        self.move(center_x, center_y)
        self.refresh_map()
        self.refresh_stops()

      for stop in self.nearby_stops:
        if self.stop_is_active(stop):
          self.visit_stop(stop)

      if self.num_balls > 100:
        self.move(center_x, center_y)
        self.refresh_monsters()
        li = list(self.nearby_monsters)
        for monster in li:
          if abs(monster.x - center_x) >= 128 or abs(monster.y - center_y) >= 128:
            continue
          if self.catch(monster):
            self.get_all_player_info(True)
            self.manage_monster_list(monster.species)
            self.get_all_player_info(True)

      center_y += 128 * direction
      self.move(center_x, center_y)

  def manage_monster_list(self, species):
    monsters = [m for m in self.monsters if m.species == species]
    if len(monsters) == 0:
      return

    best_monster = max(monsters, key=lambda m: m.attack + m.defense + m.stamina + m.size)

    for m in monsters:
      if m is not best_monster:
        self.transfer_monster(m)

    self.evolve_monster(best_monster)

  def evolve_monster(self, monster):
    result = self.request('EvolveMonster', EvolveMonsterRequest(id=monster.id), EvolveMonsterResponse)
    if result.ok:
      l.info("Evolved monster!")
    return result.ok

  def transfer_monster(self, monster):
      l.info("Transferring monster")
      self.request('TransferMonster', TransferMonsterRequest(id=monster.id), RawResponse)

  def find_candy(self, good_list):
    self.default_login()
    self.refresh_monsters()

    center_x = self.player.x
    center_y = self.player.y
    direction = -1
    direction2 = -1
    while True:
      self.refresh_map()
      self.refresh_stops()

      if abs(center_y) + 128 >= 2048:
        if abs(center_x) + 128 >= 2048:
          direction2 = -direction2

        direction = -direction
        center_x += 128 * direction2
        self.move(center_x, center_y)
        self.refresh_map()
        self.refresh_stops()

      if self.num_balls < 1000:
        for stop in self.nearby_stops:
          if self.stop_is_active(stop):
            self.visit_stop(stop)

      if self.num_balls > 100:
        self.move(center_x, center_y)
        self.refresh_monsters()
        li = list(self.nearby_monsters)
        for monster in li:
          if monster.species not in good_list:
            continue
          if self.catch(monster):
            self.get_all_player_info(True)

      center_y += 128 * direction
      self.move(center_x, center_y)


mapping = {}

def add_request(ident, name):
  try:
    mapping[ident] = (globals()[name + 'Request'], globals()[name + 'Response'])
  except KeyError:
    try:
      mapping[ident] = (RawRequest, globals()[name + 'Response'])
    except KeyError:
      try:
        mapping[ident] = (globals()[name + 'Request'], RawResponse)
      except KeyError:
        mapping[ident] = (RawRequest, RawResponse)

for _name, _ident in Request.RequestType.items():
  add_request(_ident, _name)

if __name__ == '__main__':
  if sys.argv[1] == 'parse':
    fname_send = sys.argv[2]
    fname_recv = sys.argv[3]
    cs = Client(open(fname_send))
    cr = Client(open(fname_recv))
    while True:
      req = cs.read_packet(Request, 2)
      cls_s, cls_r = mapping[req.type]
      inst_s = cls_s.FromString(req.data)
      inst_r = cr.read_packet(cls_r)
      print 'REQUEST:'
      print req
      print 'REQUEST PAYLOAD:'
      print inst_s
      print 'RESPONSE:'
      print inst_r
      print '___________________'
      print
  elif sys.argv[1] == 'catchemall':
    c = Client.connect()
    c.catch_em_all()
  elif sys.argv[1] == 'training':
    c = Client.connect()
    c.become_strong()
  elif sys.argv[1] == 'find_candy':
    c = Client.connect()
    c.find_candy(map(int, sys.argv[2:]))
  elif sys.argv[1] == 'count_candy':
    c = Client.connect()
    c.default_login()
    print c.treats[int(sys.argv[2])]
  elif sys.argv[1] == 'transfer_all':
    c = Client.connect()
    c.default_login()
    for mo in c.monsters:
      if mo.species == int(sys.argv[2]):
        c.transfer_monster(mo)
  elif sys.argv[1] == 'transfer_worst':
    c = Client.connect()
    c.default_login()
    c.manage_monster_list(int(sys.argv[2]))
  else:
    print 'Bad command!'
