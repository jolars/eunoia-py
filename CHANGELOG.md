# Changelog

## [0.6.0](https://github.com/jolars/eunoia-py/compare/v0.5.0...v0.6.0) (2026-08-21)

### Features
- add Eunoia 1.9 rendering features ([`1dd8d8f`](https://github.com/jolars/eunoia-py/commit/1dd8d8fef620238e8a06ec93d5bbee7053c13371))
- add interactive plotly backend ([`edfd6e8`](https://github.com/jolars/eunoia-py/commit/edfd6e87dfea3cee7fbc816015fa277538951e74))
- draw set members inside diagram regions ([`57b8985`](https://github.com/jolars/eunoia-py/commit/57b89851a679b6e825b3258d4249fc7f241c09b8))

### Bug Fixes
- apply aspect before measuring label text ([`0894bd5`](https://github.com/jolars/eunoia-py/commit/0894bd548d63bd65b5d3086bc6098f4e2741a5f5))

## [0.5.0](https://github.com/jolars/eunoia-py/compare/v0.4.0...v0.5.0) (2026-06-29)

### Features
- add support for rotated rectangles ([`7d8ed88`](https://github.com/jolars/eunoia-py/commit/7d8ed8847bbff4e366b9ae5f9bd69b24a940eca6))
- place labels with size-aware algorithm ([`4fa9dc5`](https://github.com/jolars/eunoia-py/commit/4fa9dc5862a6d7fe0cdec8be5ddb40d36b712124))
- add support for numpy bool arrays ([`8bfe019`](https://github.com/jolars/eunoia-py/commit/8bfe019dec476efb2d7fffc44b55482398dcbbb6))
- **euler:** add n_threads option for parallel fitting ([`b1ab633`](https://github.com/jolars/eunoia-py/commit/b1ab633bf88bc253731c1dfa9701c63fbb005702))

## [0.4.0](https://github.com/jolars/eunoia-py/compare/v0.3.0...v0.4.0) (2026-06-18)

### Features
- **venn:** add value-setting in input ([`d8698bb`](https://github.com/jolars/eunoia-py/commit/d8698bb0b0ceec40629d1f0d3b1bf906d182be28))

## [0.3.0](https://github.com/jolars/eunoia-py/compare/v0.2.0...v0.3.0) (2026-06-15)

### Features
- add optimizer knobs for fitting the euler diagrams ([`86edd72`](https://github.com/jolars/eunoia-py/commit/86edd7267998a368cb38705c6e708cc6071939ee))
- add dataframe input ([`002b530`](https://github.com/jolars/eunoia-py/commit/002b5306027be88918848c33634ec2de194da7af))
- **benchmarks:** matched-objective comparison vs Python Euler/Venn fitters ([`e80d235`](https://github.com/jolars/eunoia-py/commit/e80d23575255f4492f34553914c31aac2a1b796b))
- add loss= to euler() and upgrade eunoia core to 1.1 ([`e42f4db`](https://github.com/jolars/eunoia-py/commit/e42f4dbd1313ab07033fd031eae7a5a65498bbd6))

### Bug Fixes
- **plotting:** avoid label overlap by using new eunoia api ([`2ced691`](https://github.com/jolars/eunoia-py/commit/2ced691dfe85fee1cb0f60f42625da6114631973))

## [0.2.0](https://github.com/jolars/eunoia-py/compare/v0.1.0...v0.2.0) (2026-06-11)

### Features
- set default edgecolor to black ([`1068eba`](https://github.com/jolars/eunoia-py/commit/1068eba6269b7ecf12d6dfcc4974e4d816fd3f83))
- **plotting:** widen quantities to counts/percent + styling ([`47fc812`](https://github.com/jolars/eunoia-py/commit/47fc812cc2e9fe661831b03eeeb6affa7a6c8078))
- **plotting:** add eunoia.options global plotting defaults ([`b0b2f9d`](https://github.com/jolars/eunoia-py/commit/b0b2f9d896e8f279dceb6883c2337d7d7a1f986c))
- **plotting:** add per-set custom label text/style ([`ef33ae8`](https://github.com/jolars/eunoia-py/commit/ef33ae8b59c079e9d7165b1cb595abccae3ffa7f))
- **plotting:** support legends ([`e19f504`](https://github.com/jolars/eunoia-py/commit/e19f504f0519fb856455b8554d3b300c654cc801))
- **plotting:** accept vectors in styling ([`af5629e`](https://github.com/jolars/eunoia-py/commit/af5629e5d3a76043e8118be14379f98904ec63d5))
- support list-of-sets (membership) input in euler() and venn() ([`2c468a1`](https://github.com/jolars/eunoia-py/commit/2c468a1099b15db96c15bce4491ca005c0fca978))
- add square/rectangle shapes, complement, and venn() ([`cb46fb0`](https://github.com/jolars/eunoia-py/commit/cb46fb0d0b6659384de151612a4345882eb43a7c))

### Bug Fixes
- handle overlapping set/quantity labels ([`4204edc`](https://github.com/jolars/eunoia-py/commit/4204edcb44cf97ac2bb932cf100d1acb8357a5ab))

## [0.1.0](https://github.com/jolars/eunoia-py/compare/v0.0.1...v0.1.0) (2026-05-07)

### Features
- setup basic package infrastructure ([`32ce7eb`](https://github.com/jolars/eunoia-py/commit/32ce7eb0ddff9ae0c134182ef77e1afd2728d8ef))
