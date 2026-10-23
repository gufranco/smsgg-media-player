# 1.0.0 (2026-10-23)


* refactor!: rename to smsgg-media-player ([901233a](https://github.com/gufranco/smsgg-media-player/commit/901233aae7feff7588db0d44848ff98a5f5a8445))


### Bug Fixes

* **baker:** tune game gear dials on its colours ([cfa4566](https://github.com/gufranco/smsgg-media-player/commit/cfa45661ec5f4d2da9f83843a96be737f95ea28b))
* hold the game gear to every gate ([0ebf8b1](https://github.com/gufranco/smsgg-media-player/commit/0ebf8b1772abb84e4b0df4986d2fd96e5a1f9dc4)), closes [#ifdef](https://github.com/gufranco/smsgg-media-player/issues/ifdef)
* **player:** keep the overlay inside the GG window ([e9aca68](https://github.com/gufranco/smsgg-media-player/commit/e9aca68efc482ee3e89d145df4b4cbb0f3f254a6))
* **quantise:** dither the master system by light ([78681ad](https://github.com/gufranco/smsgg-media-player/commit/78681ad5f12fda0cb8467cfcc54b69769e1ef91e))
* rebind dial reports to each run's output ([3674e4b](https://github.com/gufranco/smsgg-media-player/commit/3674e4bd20dbf8a5b457032892367e8fc5f2d783))


### Features

* **baker:** bake for the Game Gear, --target gg ([1ee62c7](https://github.com/gufranco/smsgg-media-player/commit/1ee62c77e43bc32282679837c627444e42cab5d5))
* **baker:** Game Gear palettes from 4096 colours ([5a0a728](https://github.com/gufranco/smsgg-media-player/commit/5a0a72853f033b42e9163f66cd62c3528bc80835))
* bundle a film for a game gear game ([0ad6f76](https://github.com/gufranco/smsgg-media-player/commit/0ad6f76c3cfaada1a49829a80ba0191a88f13cf0))
* burn subtitles into the picture ([3200f8a](https://github.com/gufranco/smsgg-media-player/commit/3200f8ac3029b0298aba3f5086ac396ad71ceb51))
* **cartridge:** build the ROM after the bake ([3cecd1f](https://github.com/gufranco/smsgg-media-player/commit/3cecd1f235b534de7dd959c71676f5d591205650))
* crop bars baked into the source ([8c51f59](https://github.com/gufranco/smsgg-media-player/commit/8c51f59dfa48360934db8aa0b75900aa2342f7b2))
* emit a drop-in bundle for your own game ([114d0fe](https://github.com/gufranco/smsgg-media-player/commit/114d0fe1baf1af133c67ebe741402eaba930aaf5))
* explain every flag and a soundless source ([51a41aa](https://github.com/gufranco/smsgg-media-player/commit/51a41aa224d8782e483809e4481197f124efb2a9))
* full motion video for the Master System ([af58a38](https://github.com/gufranco/smsgg-media-player/commit/af58a386fa8b407310c4f5fc7a3faca24937e414))
* **menu:** draw the neo geo menu on sms and gg ([a8ff8b5](https://github.com/gufranco/smsgg-media-player/commit/a8ff8b5db550513d9d4dd7a324710175190cbc67))
* **menu:** make the menu an opt-in bake flag ([3f67bf0](https://github.com/gufranco/smsgg-media-player/commit/3f67bf08dda297e06b265375e250ada98a4e2e52))
* **palettes:** dither between palette entries ([55b9ead](https://github.com/gufranco/smsgg-media-player/commit/55b9ead34fb03b42e71d813b435e089d0082f057))
* pan psg channels on game gear headphones ([12e3be5](https://github.com/gufranco/smsgg-media-player/commit/12e3be5f00489bf65b91764b379377f0904f2e15))
* pause on the pause button, mute on up ([8c7142d](https://github.com/gufranco/smsgg-media-player/commit/8c7142d38d1bf76c16f688c8f50d859afb8d9e3f))
* play the soundtrack on the psg ([2a80ea1](https://github.com/gufranco/smsgg-media-player/commit/2a80ea165ce7e80adde8c53b1544fa4535eb5fd3))
* **player:** build the player for the Game Gear ([2b9d20f](https://github.com/gufranco/smsgg-media-player/commit/2b9d20f45e40d7f996fce31a9561e8b32f00fcbc))
* **player:** show the overlay during play ([c4ded71](https://github.com/gufranco/smsgg-media-player/commit/c4ded71541941beeb658678b3193ed1af9751831))
* preview every field as a video ([3d1eedf](https://github.com/gufranco/smsgg-media-player/commit/3d1eedfcb62156f8a927919110a18c3b5a285310))
* seek between keyframes on left and right ([0a83b5f](https://github.com/gufranco/smsgg-media-player/commit/0a83b5f4242a49c7aa660dd564262e67bd05e9b6))
* show a position bar while paused ([e4e0fd6](https://github.com/gufranco/smsgg-media-player/commit/e4e0fd635678fa8ef7d4e3c0195ee41eb80eb93a))
* show diagnostics on button 1 while paused ([cdb1bb1](https://github.com/gufranco/smsgg-media-player/commit/cdb1bb149e70c4a6908db91f013bd23898e27fb1))
* **sound:** track notes and follow loudness ([c1ebec4](https://github.com/gufranco/smsgg-media-player/commit/c1ebec4c8589cdfc5e5ccb156412b56723611e0a))
* step the frame rate down until a film fits ([6109eb2](https://github.com/gufranco/smsgg-media-player/commit/6109eb2b837f9db7ecb7931ec953253f911e5b65))


### BREAKING CHANGES

* the bake command is python -m smsggmedia.cartridge,
and the SMSMEDIA_ environment variables are now SMSGGMEDIA_.

# Releases

Generated from commit subjects by semantic-release, one entry per
version. What the project tried and rejected is in
[CHANGELOG.md](CHANGELOG.md); this file is only the version history.

<!-- version list -->
