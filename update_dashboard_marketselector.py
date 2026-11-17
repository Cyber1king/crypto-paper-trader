import sys

# Read the file
with open(r'C:\Users\Survival\Documents\Default Project\crypto-paper-trader\artifacts\crypto-paper-lab\src\pages\dashboard.tsx', 'r') as f:
    content = f.read()

lines = content.split('\n')

# 1. Add MarketId, allMarkets, marketLabels to the import from @/lib/markets
# Current import on lines 58-67 imports from "@/lib/markets" but only selects specific named imports
# We need to add MarketId, allMarkets, marketLabels

# Find the import line for "@/lib/markets" related items
# The imports from "@/lib/markets" are currently imported via the big import block on lines 58-77
# Actually looking at the code, the imports are on lines 58-104, and "@/lib/markets" is not directly imported
# We need to add a new import line

# Let me check what's currently imported from "@/lib/markets" - actually it's not directly imported
# The markets.ts is used implicitly. Let me add the import.

# Actually, looking at the file, the imports from "@/lib/markets" don't exist yet.
# I need to add: import { MarketId, allMarkets, marketLabels } from "@/lib/markets";

# Let me add it after the existing api.ts import block

# Insert after line 77 (after the last import from "@/lib/api")
# The existing imports from "@/lib/api" end at line 77 with "type ModesResponse"

# Find the line "import { ... } from "@/lib/api";" and add the markets import after it

# Actually, let me just add the import line
# The imports section is lines 35-105

# Let me find the right place - after "import { ... } from "@/lib/api";" which ends the api imports
# and before "import { ... } from "@/lib/hooks";"

# I'll add the markets import after line 77 (the closing of api imports)

# Let me be precise: I need to add one import line
import_line = 'import { MarketId, allMarkets, marketLabels } from "@/lib/markets";'

# Find the line "import { describeError, isApiError, type ApiError, type MarketQuery, type ModeInfo, type ModesResponse } from "@/lib/api";"
# and insert after it

# Actually, looking at the file structure, the imports from "@/lib/api" are on lines 70-77
# and the imports from "@/lib/hooks" are on lines 78-104

# I'll add the markets import line after line 77 (after the api imports block)

# Let me just use string replacement to add the import

# New import line to add
new_import = 'import { MarketId, allMarkets, marketLabels } from "@/lib/markets";'

# Insert after the api imports block
# The api imports block ends at line 77 with 'type ModesResponse},'
# I'll insert the new import after line 77

# Let me find the exact text to replace
old_text = '''import { describeError, isApiError, type ApiError, type MarketQuery, type ModeInfo, type ModesResponse } from "@/lib/api";
import { firstError, queryKeys, queryError, useAiState, useAutoStep, useDailyTargetConfig, useDailyTargetState, useHighRiskConfig, useHighRiskState, useManualActions, useManualState, useHealth, useMarket, useModes, useReplayControls, useReplayState, useRunningPolling, useSelectedMode, useStandardAccount, useStatistics, useTrades, useResearchEvidence, useResearchGovernance, useResearchProviders, } from "@/lib/hooks";
import { useQueryClient } from "@tanstack/react-query";'''

new_text = '''import { MarketId, allMarkets, marketLabels } from "@/lib/markets";
import { describeError, isApiError, type ApiError, type MarketQuery, type ModeInfo, type ModesResponse } from "@/lib/api";
import { firstError, queryKeys, queryError, useAiState, useAutoStep, useDailyTargetConfig, useDailyTargetState, useHighRiskConfig, useHighRiskState, useManualActions, useManualState, useHealth, useMarket, useModes, useReplayControls, useReplayState, useRunningPolling, useSelectedMode, useStandardAccount, useStatistics, useTrades, useResearchEvidence, useResearchGovernance, useResearchProviders, } from "@/lib/hooks";
import { useQueryClient } from "@tanstack/react-query";'''

content = content.replace(old_text, new_text)

# 2. Add useState for selectedMarket after the existing useState declarations
# Current: const [selectedMode, setSelectedMode] = useState<string>("standard");
# const [stepCount, setStepCount] = useState(1);

# I need to add: const [selectedMarket, setSelectedMarket] = useState<MarketId>('BTC/USDT');
# But TypeScript type... let me use string for simplicity

# Find the line with selectedMode and add market state after it

selected_mode_line = 'const [selectedMode, setSelectedMode] = useState<string>("standard");'
new_selected_mode_line = '''const [selectedMode, setSelectedMode] = useState<string>("standard");
const [selectedMarket, setSelectedMarket] = useState<MarketId>("BTC/USDT");'''

content = content.replace(selected_mode_line, new_selected_mode_line)

# 3. Add MarketSelector rendering in the header
# The header has right group: {healthBadge} + {StandardHeaderBalance(mode, replay.data, account.data)}
# I need to add MarketSelector there

# Find the right group div: <div className="flex items-center gap-4 min-w-0 shrink">
# and add MarketSelector after healthBadge and before StandardHeaderBalance

# The right group currently is:
# <div className="flex items-center gap-4 min-w-0 shrink">
#   {healthBadge}
#   {StandardHeaderBalance(mode, replay.data, account.data)}
# </div>

# I'll add MarketSelector after healthBadge

# Actually, let me look at the header structure more carefully.
# The header has:
# <header className="border-b bg-card sticky top-0 z-10 px-6 py-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
#   <div className="flex items-center gap-3 min-w-0">  <-- left group (title + simulated env)
#     ...
#   </div>
#   <div className="flex items-center gap-4 min-w-0 shrink">  <-- right group (health + balance)
#     {healthBadge}
#     {StandardHeaderBalance(mode, replay.data, account.data)}
#   </div>
# </header>

# I need to add MarketSelector to the right group.

# Let me find the right group div and add MarketSelector
# The right group div starts with '<div className="flex items-center gap-4 min-w-0 shrink">'

right_group_start = '<div className="flex items-center gap-4 min-w-0 shrink">'
right_group_end = '</div>'

# Current content in right group:
#   {healthBadge}
#   {StandardHeaderBalance(mode, replay.data, account.data)}

# I'll add MarketSelector after healthBadge

# Let me replace the right group content
old_right_group = '''<div className="flex items-center gap-4 min-w-0 shrink">
          {healthBadge}
          {StandardHeaderBalance(mode, replay.data, account.data)}
        </div>'''

new_right_group = '''<div className="flex items-center gap-4 min-w-0 shrink">
          {healthBadge}
          <MarketSelector defaultMarket={selectedMarket} onMarketSelect={(market) => setSelectedMarket(market)} />
          {StandardHeaderBalance(mode, replay.data, account.data)}
        </div>'''

content = content.replace(old_right_group, new_right_group)

# 3b. Also need to handle the onMarketSelect event - the MarketSelector component from market-selector.tsx
# actually has a different API. Let me check what props it expects.
# From the earlier read, MarketSelector has: defaultMarket? and internal state.
# It doesn't have onMarketSelect prop. It just has defaultMarket and manages its own state.
# But the user wants the dashboard to manage the state and pass it down.

# Actually, looking at the MarketSelector component more carefully:
# it has: defaultMarket? prop, and internal useState for selected market.
# It displays "Selected market: {marketLabels[selected]}" and "Available markets: ..."
# It doesn't have an onMarketSelect prop - it's a controlled component via defaultMarket only.

# But wait, the user said: "Ensure the selected market state is managed in dashboard.tsx (via useState) and passed down to the MarketSelector."

# So I need to pass defaultMarket prop and also handle the state update.
# But the MarketSelector component doesn't have onMarketSelect... 

# Let me re-read the MarketSelector component. It has:
# const [selected, setSelected] = React.useState<MarketId>(...)
# const handleSelect = (market: MarketId) => { setSelected(market); }
# And it renders: <div>Selected market: {marketLabels[selected]}</div>

# So it has internal state and a handleSelect, but no onMarketSelect prop exposed.
# The user wants me to manage state in dashboard.tsx and pass down.

# I think the approach should be:
# - Use the MarketSelector with defaultMarket prop
# - But also we need some way to update it
# - Perhaps I should just add the MarketSelector with defaultMarket and not worry about the onSelect
# - Or I could modify the approach

# Actually, looking more carefully at the task: "Re-integrate the <MarketSelector /> into the dashboard header (next to or near the 'Simulated Environment' label / 'API Online' badge)."

# And: "Ensure the selected market state is managed in dashboard.tsx (via useState) and passed down to the MarketSelector."

# So I need to pass defaultMarket and also some way to update it. But the MarketSelector component doesn't expose onMarketSelect.

# Let me think... Maybe I should just add the MarketSelector with defaultMarket, and the state management can be added later, or I should use the handleSelect differently.

# Actually, wait - the MarketSelector I read has:
# <div>Selected market: {marketLabels[selected]}</div>
# <div>Available markets: {available.map((m) => marketLabels[m]).join(", ")}</div>

# And it has handleSelect internal. But no props for onSelect.

# Maybe I should just add the MarketSelector with defaultMarket, and not worry about the update mechanism for now, 
# or I could add a ref or something.

# Let me just proceed with adding the MarketSelector with defaultMarket prop, 
# and note that the onSelect handling would require component modification.

# Actually, looking at this more carefully - the task says "passed down to the MarketSelector". 
# Maybe I should just add it with defaultMarket and the state management will work through the defaultMarket prop.

# Let me just add the MarketSelector import and usage, with defaultMarket set to selectedMarket.

# The MarketSelector expects: defaultMarket?: MarketId;

# So I'll add: <MarketSelector defaultMarket={selectedMarket} />

# And the state selectedMarket is already managed by useState.

# But the MarketSelector also has its own internal state... hmm.

# Let me just do the minimal changes:
# 1. Add import
# 2. Add useState for selectedMarket
# 3. Add MarketSelector in header with defaultMarket prop

# For the onMarketSelect, I'll just add it and see if it compiles, then we can handle the event handling later.

# Actually, let me re-examine - maybe I should just add the MarketSelector simply and not overthink the state sync,
# since the task says "passed down to the MarketSelector" and the component has defaultMarket.

# Let me proceed with the edits I can make work.

# 4. Run tsc to verify

# Let me do the edits step by step and then run tsc.

print("Making edits...")
print(f"File length: {len(content)}")
print(f"Lines: {len(lines)}")
"