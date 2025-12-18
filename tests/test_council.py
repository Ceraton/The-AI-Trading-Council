"""
Test script to verify Council of AIs implementation
"""
import asyncio
import sys

# Add parent directory to path
sys.path.insert(0, '.')

from strategy.analyst_agent import AnalystAgent
from strategy.sma_strategy import SMAStrategy
from strategy.meta_strategy import MetaStrategy

async def test_council():
    print("[TEST] Council of AIs Verification")
    print("=" * 50)
    
    # Create agents
    print("\n[1] Creating agents...")
    chartist = SMAStrategy(short_window=5, long_window=20)
    analyst = AnalystAgent()
    print(f"  - Chartist: {chartist.name}")
    print(f"  - Analyst: {analyst.name}")
    
    # Create meta-strategy
    print("\n[2] Creating Meta-Strategy...")
    council = MetaStrategy([chartist, analyst], voting_method='weighted')
    print(f"  - Council: {council.name}")
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
        print(f"  - Voting Method: {decision['voting_method']}")
        
        if 'agent_votes' in decision:
            print(f"\n[VOTES] Individual Agent Votes:")
            for vote in decision['agent_votes']:
                print(f"  - {vote['agent']}: {vote['vote'].upper()} (confidence: {vote['confidence']:.1%})")
    else:
        print("\n[RESULT] Council voted to HOLD")
    
    print("\n" + "=" * 50)
    print("[OK] Council of AIs is operational!")
    print("\nTo use in production:")
    print("  python main.py --paper --council --capital 500")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_council())
