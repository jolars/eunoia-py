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
  # renders nothing in a plain REPL. Pin an interactive backend (tkinter is
  # in the python package above; switch to QtAgg if you add pyqt6).
  env.MPLBACKEND = "QtAgg";

  languages = {
    python = {
      enable = true;

      package = (
        pkgs.python3.withPackages (
          ps: with ps; [
            pyqt6
          ]
        )
      );

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
