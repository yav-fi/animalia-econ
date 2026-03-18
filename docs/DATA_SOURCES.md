# Data Sources (OpenTree-first baseline)

This project can run without TraitBank, FishBase, ZooTraits, Catalogue of Life, or GloBI.

## Primary backbone (default)
- Open Tree of Life taxonomy only (Metazoa/Animalia branch), with release-versioned snapshots.

## Optional auxiliary sources (not required for baseline)
- Open Traits Network metadata (for trait discovery only)
- AVONET (birds)
- EltonTraits (birds + mammals)
- Amniote life-history database (birds + mammals + reptiles)

## Policy
- Higher-taxon priors are the default release product.
- Species values are inherited from higher ranks unless direct evidence is strong enough.
