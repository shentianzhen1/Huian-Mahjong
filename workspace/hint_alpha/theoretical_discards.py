"""Offline structural explanations; never estimates unseen remaining copies."""
from workspace.ai import analyze_effective_tiles


def explain_theoretical_discards(row):
    if not row.get('display_allowed') or row.get('hint', {}).get('phase') != 'POST_DRAW':
        return None
    snapshot = row['snapshot']
    choices = []
    for candidate in row['hint']['best_discards']:
        reduced = list(snapshot['own_hand'])
        discard = candidate['discard']
        reduced.remove(discard)
        analysis = analyze_effective_tiles(reduced, gold_tile=snapshot['gold_tile'],
            open_melds=len(snapshot['melds'][0]), visible_tiles=(discard,))
        choices.append({'discard': discard,
            'theoretical_effective_types': [item.tile for item in analysis.effective_tiles],
            'theoretical_type_count': len(analysis.effective_tiles)})
    return {'candidates': choices, 'remaining_copies_unknown': True,
        'public_remainders_used': False, 'strategy_ranking': False,
        'scope': 'Structural possibilities excluding concealed copies and the proposed discard; unknown public and meld identities are not estimated.',
        'development_only': True, 'safe_for_executor': False}
