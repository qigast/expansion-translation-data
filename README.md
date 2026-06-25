# `pokeemeraude-expansion` Translation Workspace
## About
This repository contains my personal workspace for translating the `pokeemerald-expansion` project maintained by RHH. It contains my scripts and my dumps from various sources, including PokéAPI, PokéCorpus, and of course the original `pokeemeraude`.

## Directory Structure
```
.
|- corpus/         # Contains my dumps from PokéCorpus.
|- dump/           # Contains my dumps from PokéAPI, udpated and filled with PokéCorpus data.
    |- */
        |- *.data.json  # Contains the data dumps.
        |- *.names.json # Contains the names map for batch replacement.
        |- missing.txt  # Contains the missing field errors when dumping/processing.
|- scripts/        # Contains my scripts for dumping and processing data.
```

## Scripts
Each script's purpose is (or will be) documented inside the script itself.