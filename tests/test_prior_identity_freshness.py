import copy
import unittest
from workspace.hint_alpha.live_guard import eligible_prior_identity


class PriorIdentityFreshnessTests(unittest.TestCase):
    def test_only_fresh_same_burst_real_identities_are_used(self):
        current = dict(session='s', stream_epoch=1, frames=[1,2,3],
            geometry_untrusted=False, components=[dict(region_candidate='hand', frame=3)])
        prior = {**current, 'components':[dict(region_candidate='hand', frame=2)]}
        report = {**current, 'prior_identity_report':prior, 'prior_identity_captured':10.1}
        def check(r, previous=10.):
            return eligible_prior_identity(r,captured=10.2,previous_captured=previous,now=10.3,max_age=2.)
        self.assertIs(check(report),prior)
        self.assertIsNone(check(report,previous=10.1))
        for key,value in [('session','other'),('stream_epoch',2),('frames',[0,2,3]),
                          ('geometry_untrusted',True),('components',[dict(region_candidate='hand',frame=3)])]:
            altered=copy.deepcopy(report);altered['prior_identity_report'][key]=value
            with self.subTest(key=key):self.assertIsNone(check(altered))
        for timestamp in [float('nan'),8.,10.2,True]:
            self.assertIsNone(check({**report,'prior_identity_captured':timestamp}))
