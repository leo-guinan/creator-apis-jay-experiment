# **1\. Project objective**

Build a small, malleable marketing/learning sandbox that can answer one question:

> **Can Leo turn human insight into content, turn content into measurable business value, and return some of that value to the humans whose insight helped create it—while reducing the amount of Leo-time required?**

The first live test uses the conversation with Jay Yang.

Jay’s core recommendation was to create more legible business proof: build the AI business to roughly \$10K/month, narrow the audience and promise, and document the process publicly so proof creates its own momentum. Pasted text(20261007-170828) Pasted text(20261007-170828)

Leo’s experiment deliberately escalates that:

> **Use Jay-derived content to attempt to generate 100 × \$1,000 engagements \= \$100K attributable revenue, with a 10% royalty allocated to Jay on directly attributable revenue.**

The deeper test is not simply sales. It is **time compression**:

> Can prior thinking be compressed into reusable content and systems that continue generating revenue and information while Leo is away from work?

---

# **2\. Core architectural principle**

The architecture should be:

**event-first, channel-agnostic, provenance-aware, attribution-flexible.**

The most important separations are:

**Artifact ≠ Placement**  
A video exists independently of YouTube, LinkedIn, X, or ads.

**Observation ≠ Attribution**  
Store what happened first. Decide how much credit each source deserves later.

**Content ≠ Distribution**  
Content blocks should be reusable across different channels and campaigns.

**Human source ≠ AI infrastructure**  
Humans remain visible. Marvin stays backstage.

The conceptual pipeline is:

**Source → Content Block → Artifact → Placement → Route → Event → Conversion → Attribution → Royalty**

---

# **3\. Core entities**

| Entity | Purpose |
| ----- | ----- |
| **Source** | Original human contribution: Jay interview, customer conversation, research note, etc. |
| **Contributor** | Human who contributed the source or insight. |
| **Content Block** | Reusable component: hook, story, proof, mechanism, CTA, clip. |
| **Artifact** | A complete created thing: YouTube video, short, VSL, tweet, LinkedIn post, landing page. |
| **Placement** | One artifact published somewhere specific. |
| **Channel** | YouTube, X, LinkedIn, email, paid ads, etc. |
| **Campaign** | Bounded business objective grouping artifacts and experiments. |
| **Experiment** | Explicit hypothesis tested through one or more placements. |
| **Route** | Trackable redirect/link connecting placement to destination. |
| **Offer** | Commercial destination, initially \$1,000 leverage calibration. |
| **Event** | Append-only observation of user/system behavior. |
| **Visitor / Session** | Known or anonymous traffic path when available. |
| **Lead / Customer** | Human moving through the funnel. |
| **Conversion** | Purchase, subscription, booking, etc. |
| **Provenance Edge** | Relationship such as `derived_from`, `quotes`, `responds_to`, `inspired_by`. |
| **Attribution Result** | Calculated interpretation of which sources contributed to a conversion. |
| **Royalty Rule** | Rule assigning economic participation to a contributor. |
| **Royalty Ledger** | Amount accrued/paid under a royalty rule. |

---

# **4\. Stable IDs**

Everything should have a stable internal ID before touching external platforms.

Example:

campaign: jay\_14day\_001

source: jay\_interview\_2026\_10\_07

artifact:  
  jay\_10k\_clip\_v1  
  ai\_roi\_vsl\_v1  
  proof\_of\_work\_not\_done\_v1

placement:  
  yt\_jay\_10k\_clip\_v1  
  li\_jay\_10k\_clip\_v1  
  x\_jay\_10k\_clip\_v1

experiment:  
  exp\_ai\_roi\_work\_am  
  exp\_ai\_roi\_education\_pm

route:  
  r\_jay\_youtube\_airoi\_001

offer:  
  leverage\_calibration\_1000

External identifiers—YouTube video ID, tweet ID, LinkedIn post ID—should be stored against the internal placement.

Never make external IDs the core identity.

---

# **5\. Content architecture**

Content should be modular.

A video is assembled conceptually from blocks such as:

HOOK  
PROBLEM  
STORY  
PROOF  
MECHANISM  
OFFER  
CTA

Example reusable blocks:

hook\_ai\_spend  
hook\_ai\_acceleration  
hook\_business\_worse\_with\_ai  
hook\_founder\_bottleneck

story\_jay\_homework  
story\_copy\_ai  
story\_first\_1000\_client

proof\_first\_customer  
proof\_engineering\_history  
proof\_fair\_week

mechanism\_work\_not\_done  
mechanism\_time\_back\_revenue\_in  
mechanism\_1000\_to\_250

cta\_existing\_business  
cta\_bipu

An artifact then stores which blocks it contains.

Example:

ai\_roi\_vsl\_v3 \=  
    hook\_ai\_spend  
  \+ story\_copy\_ai  
  \+ mechanism\_work\_not\_done  
  \+ mechanism\_1000\_to\_250  
  \+ cta\_existing\_business

This allows analysis at both levels:

**Which videos convert?**

and eventually:

**Which human-created blocks consistently appear in converting videos?**

That is highly relevant to Creator APIs.

---

# **6\. Placement model**

Artifacts remain channel-independent.

A placement contains:

artifact\_id  
channel  
external\_id  
publish\_time  
campaign\_id  
experiment\_id  
route\_id  
organic\_or\_paid  
audience\_variant

A single artifact might have:

YouTube organic  
X native  
LinkedIn native  
YouTube paid  
LinkedIn paid

without duplicating the artifact.

This is essential because the future question is not merely:

> Which YouTube video worked?

It is:

> Which idea worked, under which distribution conditions?

---

# **7\. Route / tracking layer**

Build a simple first-party redirect layer.

Example:

/r/abc123

Internally it stores:

campaign\_id  
artifact\_id  
placement\_id  
experiment\_id  
destination  
offer\_id  
landing\_page\_variant

Benefits:

* attribution survives destination changes  
* X/LinkedIn/YouTube can use different routes  
* the same video can test multiple VSLs  
* historical links remain valid  
* routes can later become Creator APIs provenance endpoints

For the first implementation, routes can simply issue a redirect after logging the click.

---

# **8\. Event ledger**

Events should be append-only.

Do not overwrite history to reflect current attribution beliefs.

Useful initial event types:

placement\_published  
impression  
video\_view  
meaningful\_video\_view  
route\_click  
landing\_page\_view  
vsl\_start  
vsl\_complete  
checkout\_start  
purchase\_1000  
calibration\_started  
leverage\_target\_reached  
converted\_250  
renewed\_250  
canceled\_250  
email\_reply  
qualified\_lead

Event shape:

event\_id  
timestamp  
event\_type

campaign\_id  
experiment\_id  
artifact\_id  
placement\_id  
route\_id  
offer\_id

session\_id  
visitor\_id  
customer\_id

metadata\_json

Missing identifiers are allowed.

The ledger records reality even when attribution is incomplete.

---

# **9\. Attribution model**

Do not try to solve attribution perfectly in v0.

Start with three buckets:

### **Direct**

Strong causal evidence:

specific placement  
→ tracked route  
→ session  
→ purchase

This is the initial basis for the Jay royalty.

### **Assisted**

Known customer touched the Jay-derived ecosystem, but conversion path is incomplete.

Example:

Jay video  
→ channel subscription  
→ unrelated later video  
→ offer  
→ sale

Useful analytically, but not necessarily paid under the initial direct-attribution rule.

### **Unknown**

Conversion happened but reliable provenance is unavailable.

Keep it.

Never fabricate attribution simply to make the Creator APIs story work.

---

# **10\. Royalty model**

Initial rule:

> **10% of directly attributable collected revenue produced by Jay-derived content accrues to Jay.**

So:

1 × \$1,000 sale \= \$100 Jay royalty  
10 sales \= \$1,000  
100 sales \= \$10,000

Later recurring rule can test:

> A defined percentage of retained \$250/month revenue continues accruing to Jay for customers whose origin remains directly attributable to his contribution.

Separate:

**origin attribution**

from:

**maintenance attribution.**

Jay may contribute to customer creation.

Operators/Leo/system contribute to retention.

Creator APIs eventually needs to model both.

---

# **11\. Adapter architecture**

Adapters should isolate external platforms.

Every adapter should ideally implement some version of:

publish(placement)  
sync(placement)

Publishing can remain manual initially.

The important operation early is `sync`.

### **YouTube adapter**

Maps:

internal placement  
↔ YouTube video ID

Pulls:

views  
impressions  
CTR  
watch time  
retention  
subscribers gained  
traffic sources

### **X adapter**

Maps artifact → tweet.

Pulls basic engagement/click metrics where available.

### **LinkedIn adapter**

Maps artifact → LinkedIn post.

Pulls available engagement/click metrics.

### **Payment adapter**

Initially Stripe or whichever checkout system is used.

Maps:

checkout  
purchase  
customer  
subscription  
renewal

into internal events.

### **Email adapter**

Later:

customer email  
→ business context  
→ Marvin processing  
→ Leo review  
→ response

This may ultimately become the primary service interface.

---

# **12\. Marvin's role**

Do not expose Marvin as a product.

The customer-facing product is essentially:

# **Leo as a Service**

Promise:

> Leo learns your business, identifies leverage, and helps remove unnecessary work.

Marvin exists behind Leo and should increasingly handle:

memory  
business modeling  
pattern recognition  
experiment history  
drafting  
context retrieval  
measurement  
recommendation preparation  
follow-up preparation

Desired trust progression:

Leo writes  
↓  
Marvin drafts, Leo rewrites  
↓  
Marvin drafts, Leo edits  
↓  
Marvin drafts, Leo approves  
↓  
bounded routine responses may eventually run under predefined approval rules

A key internal metric should therefore be:

> **Leo minutes required per customer per month**

The system succeeds if:

**customer leverage ↑**

while:

**Leo time/customer ↓**

---

# **13\. Offer architecture**

The free coaching hour is removed.

The core offer is:

> **Pay \$1,000. Leo will learn the business, identify leverage opportunities, and keep working through the calibration until at least \$1,000 of mutually agreed measurable value has been identified and implemented through time returned \+ revenue added.**

Then:

> **\$250/month to continue measuring and increasing leverage as the system learns the humans using it.**

The meaning of the two prices:

**\$1,000 \= uncertainty / learning / calibration**

**\$250 \= continued learning after the initial system is understood**

The decrease in price itself demonstrates compression.

The product should not be sold as:

AI implementation  
automation  
Marvin access  
AI consulting hours

Sell:

time back  
revenue in  
less required human work  
increasing leverage  
---

# **14\. Qualification split**

There are effectively two customer states.

### **Existing operating business**

Has:

customers  
recurring work  
revenue  
repeatable decisions  
operating cadence

Route to:

# **Leo as a Service / \$1K calibration**

Core question:

> **Why does this business still require so much of you?**

### **Not yet operating something worth optimizing**

Does not yet control enough:

time  
business  
distribution  
revenue  
operating system

Route to:

# **Build In Public University**

Core goal:

> Learn to create agency and build something worth owning.

This is the clean BIPU / service boundary.

Marvin is not the thing separating them.

---

# **15\. The two-week experiment**

The experiment has two phases.

## **Phase 1 — build the machine**

Before the county fair:

Create enough artifacts, placements, routes, landing pages and scheduled content that the system can operate for seven days with minimal intervention.

Goal:

> **Compress the current learning into infrastructure.**

## **Phase 2 — remove Leo**

During fair week:

Leo spends meaningful time away with family.

The marketing system continues publishing and collecting data.

Constraint:

> Avoid reactive content creation and funnel tinkering during the observation period unless required for customer service or genuinely urgent operational issues.

The absence itself becomes part of the test.

---

# **16\. Fair-week content schedule**

Two YouTube videos each day.

### **Morning**

**Work / proof**

Show something actually being done.

Examples:

building the \$1K offer  
implementing Jay's advice  
building VSL variants  
mapping recurring work  
scheduling content  
setting up measurement  
removing Leo from the loop

### **Evening**

**Educational breakdown**

Explain the principle exposed by the morning experiment.

Examples:

AI ROI  
time compression  
proof of work not done  
cheap experimentation  
operational leverage  
human-first AI  
system independence

Seven days:

**14 total experiments.**

---

# **17\. Social distribution**

Each YouTube artifact should generate a distribution packet:

YouTube  
X  
LinkedIn  
possibly native short  
possibly email

Every placement gets its own route.

This enables comparison of:

YouTube direct  
X → YouTube  
LinkedIn → YouTube  
X → VSL  
LinkedIn → VSL  
YouTube → VSL

The goal is not simply to identify a winning social network.

It is to discover:

> **What role does each network play in moving someone from attention to trust to purchase?**

---

# **18\. Organic acquisition hypothesis**

Initial conjecture:

> **0.1% qualified YouTube view → \$1,000 purchase conversion.**

Equivalent:

1,000 qualified views  
→ approximately 1 customer  
→ \$1,000 initial revenue

This is a hypothesis, not an assumed fact.

Possible internal funnel:

1,000 views  
→ 20 VSL visitors (2%)  
→ 1 purchase (5%)

or

1,000 views  
→ 50 VSL visitors (5%)  
→ 1 purchase (2%)

Track the transitions separately.

If a 1K-view video generates no sale, determine whether failure was:

views → VSL  
VSL → checkout  
checkout → purchase  
audience mismatch  
offer mismatch

Do not collapse everything into “video failed.”

---

# **19\. Video portfolio strategy**

The early optimization target is not:

> Get one video to 100K views.

It is:

> **Produce many independent attempts at earning \~1,000 qualified views.**

Each video should test something.

Potential pain hooks:

AI spend increasing without measurable ROI  
business working worse in the age of AI  
feeling rushed by technological acceleration  
founder still being the bottleneck  
automation creating more systems to maintain  
AI content treadmill without revenue  
agency headcount scaling with customers  
tool overload

The same core VSL can sit behind multiple pain-specific wrappers.

---

# **20\. VSL system**

Do not make every VSL from scratch.

Use:

audience/pain-specific opening  
\+  
shared canonical middle  
\+  
audience-specific CTA

Core VSL mechanism remains:

problem  
→ AI should reduce work, not increase it  
→ Leo learns the business  
→ identify leverage  
→ test reality  
→ measure time back \+ revenue in  
→ \$1K proof phase  
→ \$250 continuous leverage

Over time, record enough modular segments to create a library that can be recombined cheaply.

---

# **21\. Fair-week success criteria**

The established personal burn rate is:

**\$100/day \= \$700/week.**

The minimum economic test is therefore:

> Can the prebuilt system generate more than \$700 of contribution during a week in which Leo materially reduces work?

But revenue is only one output.

The system should also return **information**.

At the end of fair week, Leo should know:

which pains got attention  
which videos got qualified traffic  
which placements drove VSL visits  
which VSLs converted  
which platform combinations worked  
proof video vs educational video performance  
BiPU-interest vs service-interest  
which experiments deserve replication

The ideal state is:

> **Leo leaves for a week and the business returns both money and homework.**

---

# **22\. Proof-of-work-not-done metric**

The central concept:

> **Proof of work not done \= outcomes remain stable or improve while required human work falls.**

Suggested top-level scoreboard:

Leo hours worked  
content published  
views  
qualified VSL visits  
\$1K sales  
revenue collected  
new leads  
new subscribers  
winning hypotheses discovered  
\$250 conversions  
Leo minutes/customer

The most important ratio may eventually become:

> **Economic value created / Leo hour required**

---

# **23\. Strategic conclusions from Jay**

The Jay conversation exposed several important things.

### **Jay saw two businesses**

Because Leo explained the implementation architecture, Jay naturally perceived:

Build In Public University  
\+  
AI / Marvin business

and questioned why someone would pay \$1,000 for Marvin if a student could access the same system cheaply.

That was largely a communication failure.

The better distinction is:

**BiPU sells learning and agency.**

**Leo as a Service sells responsibility for improving an operating business.**

Marvin is not a customer-facing feature.

---

### **Leo had proof blindness**

Jay recognized Leo’s engineering career and early Copy.ai experience as meaningful proof before Leo did.

Jay’s proof ladder was essentially:

Do you have the desired result?  
Have you helped someone else get it?  
Have you helped many people get it?  
Have you helped many people like me get it?

Leo had been using a stricter internal definition:

> “I don't see working there as proof I could do something. I see doing something as proof I could do something.”

Jay identified that market proof needs to be **legible**, not merely causally satisfying to Leo. Pasted text(20261007-170828)

---

### **Jay compressed the promise**

The clearest economic outcome Leo stated was:

> **Make more money with less time and energy invested.**

That became the basis for the service.

The system should therefore measure:

**time back \+ revenue in**

rather than generic “AI use.”

---

### **Jay pushed toward focus and proof**

Jay’s strongest recommendation was to get the business working clearly enough that the result itself becomes marketing.

He suggested the business should reach around \$10K/month and then become the proof behind the university. Pasted text(20261007-170828)

Leo does not need to delay BiPU.

Instead:

**Foreground:** operating business proof  
**BiPU:** observes and learns from it  
**Later:** accumulated experiment history becomes curriculum

---

# **24\. What the July material added**

The July 30 material shows that this thesis existed well before the Jay call.

At the time Leo bought Jay’s package, he was already discussing:

Humanpower  
human agency  
network intelligence  
talent networks  
future engineering  
Build In Public University  
human-first interfaces  
movies as compressed communication  
AI sitting beneath humans

For example, Leo was already describing his mandate as maximizing Humanpower and returning saved energy to humans rather than maximizing model usage. tweets\_export

He was also explicitly considering human conversation as the interface into the system rather than forcing people to interact with an AI interface. tweets\_export

And on the day of the purchase he wrote about creating a movie about “future engineering” and the origin of BiPU. tweets\_export

Therefore the Jay interaction did not create the underlying thesis.

It served as a **compression event**.

---

# **25\. The planned-collision interpretation**

The \$3K Jay package was purchased July 30\.

The value of that purchase included a future one-on-one interaction.

Leo did not know what Jay would say.

The useful planning claim is therefore not:

> “I predicted the advice.”

It is:

> **I deliberately placed a high-quality external judgment event in my future, then spent the intervening time changing the state that judgment would encounter.**

Between purchase and call:

ideas were tested  
messaging simplified  
BiPU became more concrete  
service ideas narrowed  
first \$1K customer appeared  
content systems developed  
offer architecture improved

So Jay experienced only the current snapshot.

Leo had the movie.

---

# **26\. Miracle engineering / causal compression**

Working definition:

> **Arrange causes far enough in advance that when the visible outcome arrives, an observer cannot see enough of the causal chain to explain its speed.**

From Jay’s perspective:

conversation  
→ advice  
→ unexpectedly sophisticated implementation

From Leo’s perspective:

years of research  
→ July purchase  
→ months of experiments  
→ first client  
→ Jay call  
→ rapid execution

The difference between those views produces the appearance of “magic.”

This connects to:

> **Proof of work not done.**

High-quality results delivered unusually quickly imply hidden prior compression.

---

# **27\. BiPU learning model**

The Jay experiment suggests a useful BiPU teaching loop:

Advice  
→ generate homework  
→ perform work  
→ create artifact  
→ expose artifact to reality  
→ observe result  
→ update state  
→ generate next homework

The curriculum is dynamic rather than predetermined.

A useful framing:

> **Learning is successful when your future self no longer has to redo work your past self already figured out.**

This is the educational equivalent of work not done.

---

# **28\. Human launchpad model**

The Jay relationship also suggests a distribution primitive.

Not:

famous person promotes Leo

Instead:

trusted human contributes insight  
→ Leo creates useful work from it  
→ work promotes the human's insight  
→ upstream human has incentive to share  
→ audience observes Leo's proof of work  
→ trust flows between networks

Jay is not the launchpad.

**The trusted relationship plus mutually useful public proof is the launchpad.**

Creator APIs can eventually measure and compensate this.

---

# **29\. Creator APIs first demonstration**

The initial Creator APIs story can be extremely simple:

> **How much was Jay’s insight actually worth?**

Track:

Jay interview  
→ derived content  
→ placements  
→ audience traffic  
→ \$1K purchases  
→ retained \$250 relationships  
→ attributable value  
→ royalty back to Jay

This demonstrates:

**reward people, not models.**

The key product is not merely the check.

It is:

> **The auditable causal trail explaining why the check exists.**

---

# **30\. Build order**

For the agent, I would build in this order:

1. **Database schema for core entities**  
2. **Campaign \+ experiment creation**  
3. **Artifact \+ provenance management**  
4. **Placement records**  
5. **Tracking-route redirect service**  
6. **Append-only event collector**  
7. **Offer \+ purchase/conversion recording**  
8. **Basic direct-attribution query**  
9. **Royalty ledger**  
10. **Simple experiment dashboard**  
11. **YouTube metric import**  
12. **X / LinkedIn metric import**  
13. **Email/customer workflow**  
14. **Marvin-assisted analysis**  
15. **Creator APIs packaging**

Avoid overbuilding publishing automation initially.

Manual publishing is acceptable.

**Measurement is higher leverage than automation right now.**

---

# **31\. v0 acceptance test**

The sandbox is useful when Leo can:

create one campaign  
register Jay as a contributor  
register the interview as a source

create a content block from his advice  
create a YouTube artifact from it  
publish it  
register the YouTube placement

create an X placement  
create a LinkedIn placement

generate unique routes for each

send users through those routes  
observe page views and checkout activity

record a \$1,000 purchase

trace:  
purchase  
→ route  
→ placement  
→ artifact  
→ content block  
→ Jay interview  
→ Jay

calculate:  
\$1,000 attributable revenue  
→ \$100 Jay royalty

Once that works, the fundamental Creator APIs loop exists.

Everything afterward is refinement.

---

# **32\. North-star constraints**

The agent should preserve these architectural principles even if implementation details change:

> **Humans stay in front. AI stays behind them.**

> **Artifacts exist independently of distribution channels.**

> **Raw events are preserved independently of attribution models.**

> **Provenance is stored before economic value is known.**

> **Every experiment should make the next experiment cheaper or more informed.**

> **Successful learning should reduce future human work.**

> **The system should ultimately be judged by time returned without loss of results.**

The entire project can therefore be summarized as:

**Humans provide judgment → software preserves and compounds it → markets test it → value gets measured → useful humans share in the upside → humans get more of their time back.**

