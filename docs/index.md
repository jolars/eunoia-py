# eunoia

```{toctree}
:maxdepth: 2
:hidden:
:caption: Contents

Home<self>
quickstart
gallery
api
```

Python bindings for the [eunoia](https://github.com/jolars/eunoia) Rust
library — area-proportional Euler and Venn diagrams. Sister package to the
R package [eulerr](https://github.com/jolars/eulerr).

## Install

```bash
pip install eunoia
```

## At a glance

```python
import eunoia as eu

fit = eu.euler({"A": 10, "B": 5, "A&B": 3})
print(fit)
fit.plot()
```

See {doc}`quickstart` for more examples and {doc}`api` for the reference.
