{
  description = "Terminal EPUB reader with vim-like keybindings";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python313;
      in
      {
        packages.default = python.pkgs.buildPythonApplication {
          pname = "epy";
          version = "0.1.0";
          src = ./.;
          format = "pyproject";

          nativeBuildInputs = with python.pkgs; [
            setuptools
            wheel
          ];

          propagatedBuildInputs = with python.pkgs; [
            ebooklib
            beautifulsoup4
          ];

          meta = with pkgs.lib; {
            description = "Terminal EPUB reader with vim-like keybindings";
            homepage = "https://github.com/Konecho/epy";
            license = licenses.mit;
            maintainers = [ ];
          };
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            python.pkgs.ebooklib
            python.pkgs.beautifulsoup4
            python.pkgs.pytest
            pkgs.uv
          ];
        };
      });
}
