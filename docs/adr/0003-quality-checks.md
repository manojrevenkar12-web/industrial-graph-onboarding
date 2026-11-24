# 0003 Quality checks that change the graph

## Decision
- **Duplicates** stay as `Record -same_machine_as-> Machine` aliases; nothing is deleted from the customer's master
  data. Merged automatically only when both functional locations parse to the same tag and class.
- **Renamed tags** are joined when the new series starts within 3 hours of the old one ending with no jump beyond 4
  standard deviations of the old series' steps; automatically when both names parse to the same loop, otherwise by
  the engineer. The new series inherits the old link.
- **Units**: a pressure declared in bar whose median sits in the kPa range of the plant's typical pressures is
  converted. Nothing else is converted.
- **Work orders** move only to a machine their text names (code tag, or a model quote that is in the text and
  parses). Automatic when that machine's running vibration rose around the order date and the booked machine's did
  not; otherwise the engineer confirms.

## Consequences
Development: 10 of 11 duplicates merged, 46 of 47 renames joined, 6 of 6 unit errors converted, 23 of 29 misbooked
work orders moved, 0 wrong in each. The 6 not moved name no machine in their text; nothing in the data can say where
they belong.
