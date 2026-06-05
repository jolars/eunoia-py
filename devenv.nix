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

  languages = {
    python = {
      enable = true;

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
