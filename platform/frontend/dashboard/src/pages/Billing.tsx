import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { billingApi } from '../services/api';
import { Plan } from '../types';

export default function Billing() {
  const { customer } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [currentSub, setCurrentSub] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      billingApi.getPlans().catch(() => ({ plans: [] })),
      billingApi.getCurrentPlan().catch(() => null),
    ]).then(([p, c]) => {
      setPlans(p.plans);
      setCurrentSub(c);
      setLoading(false);
    });
  }, []);

  const handleUpgrade = async (planId: string) => {
    setCheckoutLoading(planId);
    try {
      const { checkout_url } = await billingApi.createCheckout(planId);
      window.location.href = checkout_url;
    } catch (err) {
      console.error('Checkout failed:', err);
      setCheckoutLoading(null);
    }
  };

  const handleManage = async () => {
    try {
      const { portal_url } = await billingApi.createPortalSession();
      window.location.href = portal_url;
    } catch (err) {
      console.error('Portal failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-vox-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  const urlParams = new URLSearchParams(window.location.search);
  const showSuccess = urlParams.get('success') === 'true';
  const showCanceled = urlParams.get('canceled') === 'true';

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Billing & Plans</h1>
      <p className="text-gray-400 mb-8">Manage your subscription and billing</p>

      {showSuccess && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
          Subscription activated successfully! Your new plan is now active.
        </div>
      )}
      {showCanceled && (
        <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
          Checkout was canceled. No changes were made to your subscription.
        </div>
      )}

      {/* Current plan */}
      <div className="bg-[#1a1230] rounded-xl p-6 border border-vox-900/50 mb-8">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">Current Plan</p>
            <p className="text-xl font-bold text-white mt-1">{customer?.plan?.toUpperCase()}</p>
            {currentSub?.subscription && (
              <p className="text-sm text-gray-400 mt-1">
                {currentSub.subscription.status === 'active' && currentSub.subscription.current_period_end && (
                  <>Renews on {new Date(currentSub.subscription.current_period_end).toLocaleDateString()}</>
                )}
              </p>
            )}
          </div>
          {customer?.plan !== 'free' && (
            <button
              onClick={handleManage}
              className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm transition-colors"
            >
              Manage Subscription
            </button>
          )}
        </div>
      </div>

      {/* Plans grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {plans.map((plan) => {
          const isCurrent = customer?.plan === plan.id;
          const isUpgrade = !isCurrent && plan.price > 0;

          return (
            <div
              key={plan.id}
              className={`relative bg-[#1a1230] rounded-2xl p-6 border transition-all ${
                isCurrent
                  ? 'border-vox-500 ring-1 ring-vox-500/30'
                  : 'border-vox-900/50 hover:border-vox-600/50'
              }`}
            >
              {isCurrent && (
                <span className="absolute -top-3 left-6 px-3 py-1 text-xs font-medium rounded-full bg-vox-600 text-white">
                  Current Plan
                </span>
              )}

              <h3 className="text-lg font-bold text-white mt-2">{plan.name}</h3>

              <div className="mt-3 mb-5">
                {plan.price === 0 ? (
                  <span className="text-3xl font-bold text-white">Free</span>
                ) : (
                  <>
                    <span className="text-3xl font-bold text-white">${plan.price}</span>
                    <span className="text-gray-400">/mo</span>
                  </>
                )}
              </div>

              <ul className="space-y-3 mb-6">
                {plan.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <svg className="w-5 h-5 text-vox-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>

              {isCurrent ? (
                <button
                  disabled
                  className="w-full py-2.5 rounded-lg bg-vox-600/20 text-vox-300 text-sm font-medium cursor-default"
                >
                  Current Plan
                </button>
              ) : isUpgrade ? (
                <button
                  onClick={() => handleUpgrade(plan.id)}
                  disabled={checkoutLoading === plan.id}
                  className="w-full py-2.5 rounded-lg bg-vox-600 hover:bg-vox-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {checkoutLoading === plan.id ? 'Redirecting...' : `Upgrade to ${plan.name}`}
                </button>
              ) : (
                <button
                  disabled
                  className="w-full py-2.5 rounded-lg bg-gray-700/50 text-gray-400 text-sm font-medium cursor-default"
                >
                  {plan.price === 0 ? 'Free Forever' : `Contact Sales`}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
