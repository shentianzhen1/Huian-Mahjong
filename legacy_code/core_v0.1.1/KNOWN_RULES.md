# Happy Quanzhou Mahjong - Two Player / Core V0.1

## Confirmed / high-confidence
- 2 players
- 144 total tiles
- Dealer 17 tiles, non-dealer 16 tiles
- Draw game when wall reaches 16 tiles
- 8 flowers and flower replacement
- Gold is wildcard and cannot replace a flower
- Single gold can pinghu; double gold cannot pinghu
- Supports pinghu, zimo, qianggang, sanjindao, youjin, double-you, triple-you
- Real two-player settlement evidence:
  `((winner_base + winner_fan) - (loser_base + loser_fan)) * multiplier`
- Real zimo example: `(5 + 24 - 10 - 2) * 2 = 34`
- Current room displays `游金×3`

## Pending
- Chi permission in exact two-player room
- Double-you multiplier
- Triple-you multiplier
- Flower-set bonus stacking
- Exact Tian-Ting trigger
- Fan treatment of gold-assisted concealed triplets
