# sisu2gv

The script can generate [Graphviz](https://graphviz.org/) files from Tampere
University Sisu curricula database. The main use is to visualize a degree programme to better understand how the prerequisites and different modules are related.

It works by reading the data using the Sisu API and writes a gv file that 
can then be drawn to a graph visualization using Graphviz dot command.

**Disclaimer:** The software is MIT licensed and the author(s) do not guarantee that the information generated is accurate representation of programme requirements or other details. Please refer to the official [Tampere University curriculum](https://www.tuni.fi/fi/tule-opiskelemaan/opinto-oppaat) for the ground truth.

## Getting Started

Just clone the repo and the script some commands. For example:

```bash
./sisu2gv.py otm-648015d7-c210-4f5e-b83a-e5a2fc8b6526 -y 2022 -b ITC_CEE_800 -b TAU_OPN_120 -b COMP_920 -b TAU_KN_111 -b TAU_KN_121 -b TAU_KN_131 -b TAU_KN_110 -b TAU_KN_120 -b AUT_410 -b AUT_420
```

Would generate a Graphviz file for the degree programme _"Tietojenkäsittelyopin maisteriohjelma, Seinäjoki, 120 op"_. Some courses related to MSc. thesis and some outliers are blacklisted.

Another (very similar) example:

```bash
./sisu2gv.py otm-648015d7-c210-4f5e-b83a-e5a2fc8b6526 -y 2022 -b ITC_CEE_800 -b TAU_OPN_120 -b COMP_920 -b TAU_KN_111 -b TAU_KN_121 -b TAU_KN_131 -b TAU_KN_110 -b TAU_KN_120 -b AUT_410 -b AUT_420
```

Would generate a Graphviz file for its sister programme _"Tietotekniikan DI-ohjelma, Seinäjoki, 120 op"_.

See help with ```./sisu2gv.py -h``` to see additional options. For example one can give additional information for the graph generation using a json file. An [example file](additional_course_data.json) containing such extra data is provided. Feel free to extend this funcionality as needed. As of now only icons (and those only in Graphviz svg export) and additional manual course requirements are supported.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details