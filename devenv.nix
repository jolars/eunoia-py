{
  pkgs,
  ...
}:

{
  packages = [
    pkgs.bashInteractive
    pkgs.go-task
    pkgs.ruff
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
  ];

  env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
  ];

  # matplotlib defaults to the non-interactive Agg backend, so fit.plot()
  # renders nothing in a plain REPL. We want TkAgg: tkinter ships with the nix
  # interpreter below (_tkinter is part of the stdlib, so the uv venv sees it
  # even though it has include-system-site-packages = false). Don't install
  # pyqt6 via uv/pip: the wheel's QtCore.so can't find its dynamic deps (e.g.
  # libzstd.so.1) on NixOS. For Qt, add pyqt6 to the nix withPackages below and
  # flip the venv to system-site-packages instead.
  #
  # NB: this matplotlib (3.10.9) silently IGNORES MPLBACKEND and a matplotlibrc
  # backend line --- its lazy resolver falls through to Agg even though TkAgg
  # imports fine. The only thing it honors is an explicit matplotlib.use(), so
  # we force the backend from PYTHONSTARTUP. MPLBACKEND is kept as a documented
  # fallback for any code path that does read it. PYTHONSTARTUP only covers the
  # plain `python` REPL: scripts need `matplotlib.use("TkAgg")` at the top, and
  # ipython needs `%matplotlib tk`.
  env.MPLBACKEND = "TkAgg";
  env.PYTHONSTARTUP = pkgs.writeText "eunoia-pythonstartup.py" ''
    # See devenv.nix: matplotlib here ignores MPLBACKEND, so force TkAgg.
    try:
        import matplotlib

        matplotlib.use("TkAgg")
    except Exception:
        pass
  '';

  languages = {
    python = {
      enable = true;

      package = pkgs.python3.withPackages (ps: with ps; [ tkinter ]);

      uv = {
        enable = true;

        sync = {
          enable = true;
          allExtras = true;
          allGroups = true;
        };
      };

      venv = {
        enable = true;
      };
    };

    rust = {
      enable = true;
      channel = "stable";
      version = "1.88.0";
    };
  };

  git-hooks.hooks = {
    ruff.enable = true;
    ruff-format.enable = true;
  };
}
