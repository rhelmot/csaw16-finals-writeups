# Super Monster Ball

This was a set of two reversing challenges by Vector 35. We were given a client for a terminal-based Pokémon Go clone called Super Monster Ball. The gameplay is identical to Pokémon Go, but with a TUI.

The following files were provided during the CTF:

- [`game_client`](./game_client): 
- [`libprotobuf.so.11`](./libprotobuf.so.11): 
- [`remote.crt`](./remote.crt): Originally `server.crt`, the SSL certificate for securely connecting to the game server

I developed the following files to solve the challenges:

- [`request.proto`](./request.proto): The protobuf protocol definitions for this binary, obtained by running [Protod](https://github.com/sysdream/Protod) on it
- [`request_pb2.py`](./request_pb2.py): The python version of the protocol definitions, obtained by running `protoc --python_out=. request.proto`
- [`client.py`](./client.py): The client I wrote for the game. Has lots of functionality controlled through `argv[1]`, check the bottom of the file.
- [`socat.crt`](./socat.crt) and [`socat.key`](./socat.key): A keypair for my man-in-the-middle setup to use. Generated via `openssl req -newkey rsa:2048 -nodes -keyout socat.key -x509 -days 365 -out socat.crt`
- [`mitm.sh`](./mitm.sh): My man-in-the-middle script to dump out communications between the real client and the server. Running it listens on port 8080 for connections, prints out nicely-formatted traffic between the client and server, and then exits after connection close.

The source code for the client and server has since been [released](https://github.com/vector35/supermonsterball/).

There were two flags that could be obtained from this challenge. The first was given to players who successfully captured all 103 monsters, and the latter was given to players who successfully reached level 40 and defeated the "pit of doom", a difficult boss battle. If at any point the player did anything "illegal", their account would be marked for a ban, and they would not discover this until they could get the flag, which is a pretty huge dick move, especially considered we were never told what the criteria for getting banned were!

The difficulty of this challenge was first understanding all the technical moving parts to the protocol, and then implementing a client and then an algorithm to play the game. Some understanding of how pokemon battles operate was necessary to know that the final boss had max-IV max-level monsters, and knowing how to assemble a good team, search for your own max-IV monsters and level them up to the maximum.

My client can run in several modes, controlled by `argv[1]`:

- `parse`: reads from the files on the second and third args and dumps out the communications between client and server. mitm.sh uses this.
- `catchemall`: run around catching monsters until you've got all of them, then print out flag 1
- `training`: run around catching monsters until you've reached level 40. Transfer monsters with suboptimal IVs, and evolve when possible.
- `find_candy`: run around catching any of the monsters with ids given in additional args. For example, `python client.py find_candy 99 100 101`
- `count_candy`: print the number of pieces of candy for the given id, for example, `python client.py count_candy 99`
- `transfer_all`: transfer all of the monsters of the given id
- `transfer_worst`: transfer all of the monsters of the given id except for the one with the best IVs, and then evolve that one if possible

My final team for taking down the Pit of Doom was:

1. Crystrike - counter to Ogreat and Bonedread
2. Burninator - counter to Beezer
3. Krabber - counter to Ehkaybear and Burninator
4. Ohdaze - counter to Ogreat and Bonedread
5. Whalegun - counter to Ehkaybear and Burninator
6. Woofer - cute pup :3
