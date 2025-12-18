"""
Test script to verify OnChain Agent and full Council
"""
import asyncio
import sys

sys.path.insert(0, '.')

from strategy.analyst_agent import AnalystAgent
from strategy.onchain_agent import OnChainAgent
from strategy.sma_strategy import SMAStrategy
from strategy.meta_strategy import MetaStrategy

async def test_full_council():
    print("[TEST] Full Council of AIs with OnChain Agent")
    print("=" * 60)
    
    # Create all 3 agents
    print("\n[1] Creating agents...")
    chartist = SMAStrategy(short_window=5, long_window=20)
    analyst = AnalystAgent()
    onchain = OnChainAgent(network='ethereum')
    
    print(f"  - Chartist: {chartist.name}")
    print(f"  - Analyst: {analyst.name}")
    print(f"  - OnChain: {onchain.name}")
    
    # Create meta-strategy
    print("\n[2] Creating Meta-Strategy...")
    council = MetaStrategy([chartist, analyst, onchain], voting_method='weighted')
    print(f"  - Council: {council.name}")
    print(f"  - Agents: {len(council.agents)}")
    print(f"  - Voting method: weighted")
    
    # Test with sample candle
    print("\n[3] Testing with sample candle...")
    sample_candle = {
        'timestamp': 1702800000000,
        'open': 42000,
        'high': 42500,
        'low': 41800,
        'close': 42300,
        'volume': 1500000
    }
    
    decision = await council.on_candle(sample_candle)
    
    if decision:
        print(f"\n[RESULT] Council Decision:")
        print(f"  - Action: {decision['side'].upper()}")
        print(f"  - Price: ${decision['price']:,.2f}")
        print(f"  - Confidence: {decision['confidence']:.1%}")
        print(f"  - Vote Breakdown: {decision['vote_breakdown']}")
        
        if 'agent_votes' in decision:
            print(f"\n[VOTES] Individual Agent Votes:")
            for vote in decision['agent_votes']:
                print(f"  - {vote['agent']:15s}: {vote['vote'].upper():5s} (confidence: {vote['confidence']:.1%})")
                
                # Show reasoning for OnChain agent
                if vote['agent'] == 'OnChainAgent' and 'reasoning' in vote:
                    reasoning = vote['reasoning']
                    print(f"      └─ Whale Signal: {reasoning.get('whale_signal', 'N/A')}")
                    print(f"      └─ Details: {reasoning.get('details', 'N/A')}")
    else:
        print("\n[RESULT] Council voted to HOLD")
    
    # Test OnChain agent separately
    print("\n" + "=" * 60)
    print("[4] Testing OnChain Agent directly...")
    
    onchain_signal = await onchain.on_candle(sample_candle)
    if onchain_signal:
        print(f"  - Vote: {onchain_signal['vote'].upper()}")
        print(f"  - Confidence: {onchain_signal['confidence']:.1%}")
        reasoning = onchain_signal.get('reasoning', {})
        print(f"  - Whale Signal: {reasoning.get('whale_signal', 'N/A')}")
        print(f"  - Large Transfers: {reasoning.get('large_transfers', 0)}")
        print(f"  - Net Flow: ${reasoning.get('net_flow', 0):,.0f}")
        print(f"  - Details: {reasoning.get('details', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("[OK] Full Council with OnChain Agent is operational!")
    print("\nTo use in production:")
    print("  python main.py --paper --council --capital 500")
    print("\nThe Council now has 3 agents:")
    print("  1. Chartist (Technical Analysis)")
    print("  2. Analyst (Sentiment)")
    print("  3. OnChain (Whale Watching)")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_full_council())
