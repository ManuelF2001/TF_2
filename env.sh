# Source this file before running Maelstrom:   source ~/TF_2/env.sh
#
# Java 17 and gnuplot were installed in user space (~/.local/opt) for Lab 1
# (see ~/TF/env.sh) because the machine has no passwordless sudo. Lab 2
# reuses that installation and Lab 1's Maelstrom 0.2.4 (the maelstrom
# symlink next to this file points to ~/TF/maelstrom).
# With a system-wide install
#   sudo apt install openjdk-17-jre-headless gnuplot-nox graphviz
# only the MAELSTROM line is needed.

export JAVA_HOME="$HOME/.local/opt/jdk-17.0.20.1+1-jre"
export PATH="$JAVA_HOME/bin:$HOME/.local/bin:$PATH"
export MAELSTROM="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/maelstrom/maelstrom"
