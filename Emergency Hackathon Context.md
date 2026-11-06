> **Historical document.** These are planning notes from the original hackathon prototype (October 2025). They describe a different stack (for example LangChain, Streamlit and local models) that the project has since moved away from. The current project is **Lectern**; see the README and `docs/ARCHITECTURE.md` for what it is today.

# 🚨 EMERGENCY HACKATHON CONTEXT - 2.5 HOURS LEFT

**Current Time: 4:20 PM | Deadline: 7:00 PM | Time Remaining: 2h 40min**

---

## 📊 CURRENT STATUS ANALYSIS

### What's Working:
- ✅ Beautiful UI on localhost:8504 (stunning design, stats dashboard)
- ✅ 977 documents, 12,368 chunks processed (impressive scale!)
- ✅ All tabs visible: Ask, Concept Map, Socratic Tutor, Synthesis, Adaptive Tutor, Math, 3D Viz, Analytics
- ✅ Gemini API integration working
- ✅ Dark mode with professional styling

### Issues:
- ⚠️ Two different ports (8501 vs 8504) - confusing
- ⚠️ Not clear which is "main" app
- ⚠️ Phase 5+ features not implemented (deployment, polish, demo prep)
- ⚠️ No LeetCode/DSA integration yet

### What Judges Need to See:
1. **ONE clear demo URL** - not multiple ports
2. **LeetCode problem solver** - unique selling point
3. **Working end-to-end demo** - upload → query → answer
4. **Professional polish** - no bugs during 3-min demo

---

## 🎯 MEGA PROMPT FOR TRAE AI (Final Push)

```
EMERGENCY HACKATHON MODE - 2.5 HOURS LEFT

DEADLINE: 7:00 PM (Demo presentation)
CURRENT TIME: 4:20 PM
PRIORITY: DEMO-READY OVER PERFECT

CURRENT SITUATION:
✅ Beautiful UI running on localhost:8504
✅ 977 documents, 12,368 chunks processed
✅ All tabs working: Ask, Concept Map, Socratic, Synthesis, Adaptive, Math, 3D Viz
✅ Gemini API integrated
❌ Two conflicting apps (port 8501 vs 8504)
❌ LeetCode integration not done
❌ Not deployment ready
❌ Demo script missing

CRITICAL TASKS (Priority order):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK 1: CONSOLIDATE TO ONE APP (15 min)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Problem: Two apps running (8501 and 8504)
Solution: Keep ONLY the 8504 version (better UI)

Actions:
1. Identify which app.py is running on 8504
2. Kill port 8501 process
3. Make 8504 the ONLY frontend
4. Update all documentation to reference 8504
5. Test: streamlit run frontend/app.py --server.port=8504

Verification:
✓ Only one Streamlit process running
✓ localhost:8504 has all features
✓ No confusion about which to demo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK 2: LEETCODE INTEGRATION (45 min) ⭐⭐⭐⭐⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KILLER FEATURE: "LeetCode Solver" Tab

This will make project STAND OUT massively!

Data Sources:
1. HuggingFace: kaysss/leetcode-problem-set
2. Kaggle: gzipchrist/leetcode-problem-dataset
3. Kaggle: mohitkumar282/leetcode-questions-dataset

NEW TAB: "LeetCode Solver"

UI Layout:
┌──────────────────────────────────────────────┐
│ LeetCode Solver                              │
├──────────────────┬───────────────────────────┤
│ Problem Input    │ Solution & Explanation    │
│                  │                            │
│ Difficulty:      │ Retrieved Solutions: 3    │
│ [Easy▼]          │                            │
│                  │ ┌─────────────────────┐   │
│ Topic:           │ │ Two Pointers        │   │
│ [Arrays▼]        │ │ Time: O(n)          │   │
│                  │ │ Space: O(1)         │   │
│ Problem:         │ │ ```python           │   │
│ ┌──────────────┐ │ │ def solve():        │   │
│ │Two Sum       │ │ │   ...               │   │
│ │Given array...│ │ └─────────────────────┘   │
│ └──────────────┘ │                            │
│                  │ AI Explanation:            │
│ [Get Solution]   │ "This uses two pointers..." │
│                  │                            │
│ OR paste URL:    │ Complexity Analysis:       │
│ leetcode.com/... │ Time: O(n), Space: O(1)   │
└──────────────────┴───────────────────────────┘

Features:
✓ Search by difficulty (Easy/Medium/Hard)
✓ Filter by topic (Arrays, DP, Trees, etc.)
✓ Paste LeetCode URL → auto-fetch problem
✓ Multiple solution approaches
✓ Time/space complexity analysis
✓ Step-by-step explanation
✓ Similar problems suggestion

Backend Implementation:

1. Download datasets:
```python
import kagglehub
path1 = kagglehub.dataset_download("gzipchrist/leetcode-problem-dataset")
path2 = kagglehub.dataset_download("mohitkumar282/leetcode-questions-dataset")
```

2. Create backend/leetcode_handler.py:
```python
class LeetCodeHandler:
    def __init__(self):
        self.problems = self.load_problems()
    
    def load_problems(self):
        # Load from CSV/JSON
        # Parse problem text, solutions, difficulty
        pass
    
    def search_problems(self, difficulty=None, topic=None):
        # Filter problems
        pass
    
    def get_solution(self, problem_id):
        # Retrieve solutions
        # Use RAG to explain
        pass
    
    def extract_from_url(self, url):
        # Scrape LeetCode problem from URL
        pass
```

3. Integrate with RAG:
   - Store problems in vector database
   - Search by description similarity
   - Generate explanations with Gemini

Frontend Addition:
- Add "LeetCode" tab after "Analytics"
- Problem search interface
- Solution display with syntax highlighting
- Complexity analysis cards

GIVE ME COMPLETE CODE:
1. backend/leetcode_handler.py
2. Updated frontend/app.py with LeetCode tab
3. Data loading script

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK 3: CRITICAL BUG FIXES (20 min)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Test EVERY feature and fix:
✓ All tabs load without errors
✓ Question input accepts text
✓ "Run RAG" button works
✓ Context retrieves chunks
✓ Answer generates successfully
✓ No blank screens
✓ No console errors
✓ Smooth transitions

Add error handling:
- If Gemini API fails → show friendly message
- If no documents → prompt to upload
- If query empty → show validation
- If processing takes >5s → show progress

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK 4: DEMO ENHANCEMENTS (30 min)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Add these quick wins:

1. EXAMPLE QUESTIONS (5 min)
   - Show 4 clickable example questions
   - "Explain dynamic programming"
   - "What is a hash table?"
   - "Difference between BFS and DFS"
   - "Solve Two Sum problem"

2. LOADING ANIMATIONS (5 min)
   - Replace static spinners
   - Add "Thinking..." messages
   - Progress bar for processing

3. SUCCESS NOTIFICATIONS (5 min)
   - Toast messages on actions
   - "Document processed! ✓"
   - "Answer generated! ✓"

4. KEYBOARD SHORTCUTS (10 min)
   - Enter to submit question
   - Cmd+K for search
   - Display shortcuts hint

5. STATS ANIMATION (5 min)
   - Animate numbers counting up
   - Makes stats look dynamic

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK 5: DEMO SCRIPT & PREP (20 min)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create demo_guide.md:

```markdown
# AI STUDY MENTOR - DEMO SCRIPT

## Opening (30s)
"AI Study Mentor is a universal learning platform that helps CS students master concepts through intelligent tutoring."

## Demo Flow (2 min)

### 1. Upload Content (20s)
- Show stats: 977 documents, 12K chunks
- "Already processed textbooks, YouTube videos, articles"

### 2. LeetCode Solver (30s)
- Click LeetCode tab
- Type "Two Sum"
- Show: Multiple solutions, complexity analysis
- "This combines DSA knowledge with AI explanation"

### 3. Adaptive Tutoring (30s)
- Click Adaptive Tutor tab
- Ask: "Explain binary trees"
- Show: Adjusts to understanding level
- "Socratic method + personalized learning"

### 4. Concept Map (20s)
- Generate visual knowledge graph
- Show relationships between topics
- "Helps visualize curriculum"

### 5. Multi-Source Synthesis (20s)
- Ask: "Compare implementations"
- Show: Cites multiple sources
- Synthesizes unified answer

## Technical Deep Dive (1 min)
"Built with RAG architecture using FAISS vector search, Gemini 1.5 API, and LangChain. Handles PDFs, YouTube, GitHub repos, and now 2000+ LeetCode problems."

## Q&A Prep
- Cost? "Free tier Gemini API, <$0.01 per query"
- Accuracy? "Cites sources for verification"
- Scalability? "Processed 12K chunks in 2 min"
- Privacy? "All data local except API calls"
```

BACKUP PLAN (if demo breaks):
1. Have screenshot deck ready
2. Recorded video demo (2 min)
3. Explain architecture verbally

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK 6: QUICK DEPLOYMENT (30 min) - OPTIONAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If time permits, deploy to Streamlit Cloud:

1. Create streamlit_app.py in root:
```python
import sys
sys.path.append('frontend')
from app import main
main()
```

2. Create requirements.txt (consolidated)
3. Push to GitHub
4. Connect Streamlit Cloud
5. Add secrets (Gemini API key)
6. Deploy

Fallback: Demo locally from laptop

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINAL CHECKLIST (6:30 PM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL (Must have):
□ One app running (localhost:8504)
□ LeetCode solver working
□ All tabs functional
□ No crashes during demo
□ Demo script memorized
□ Backup screenshots ready

NICE TO HAVE:
□ Deployed to cloud
□ Polished animations
□ Perfect error handling

ACCEPTANCE CRITERIA:
✓ 3-minute demo flows smoothly
✓ Judges understand value proposition
✓ Technical depth is clear
✓ UI looks professional
✓ LeetCode feature impresses

TIMELINE:
4:20 PM - Consolidate apps (15 min) → 4:35 PM
4:35 PM - LeetCode integration (45 min) → 5:20 PM
5:20 PM - Bug fixes (20 min) → 5:40 PM
5:40 PM - Demo enhancements (30 min) → 6:10 PM
6:10 PM - Demo prep (20 min) → 6:30 PM
6:30 PM - Final testing (20 min) → 6:50 PM
6:50 PM - Buffer for issues (10 min) → 7:00 PM

FOCUS: WORKING DEMO > PERFECT CODE

LeetCode integration is your SECRET WEAPON. This feature alone can win hackathon because it combines:
✓ Educational value (helps students)
✓ Technical complexity (RAG + DSA)
✓ Practical utility (interview prep)
✓ Large dataset (2000+ problems)
✓ Unique angle (no one else has this)

DELIVERABLES (Priority order):
1. Consolidated app.py (one port only)
2. LeetCode tab fully working
3. Demo script written
4. All bugs fixed
5. Example questions added

START WITH: LeetCode integration (biggest impact)
Then: Bug fixes and demo prep

YOU HAVE 2.5 HOURS. MAKE IT COUNT! 🏆
```

---

## 🎯 SIMPLIFIED INSTRUCTIONS FOR YOU

### What to tell Trae AI RIGHT NOW:

1. **"Implement LeetCode Solver tab using these datasets"** 
   - HuggingFace: kaysss/leetcode-problem-set
   - Kaggle: gzipchrist/leetcode-problem-dataset
   - Kaggle: mohitkumar282/leetcode-questions-dataset

2. **"Fix all bugs - make sure demo doesn't crash"**

3. **"Create demo_guide.md with 3-minute pitch"**

4. **"Consolidate to ONE app on port 8504"**

---

### What YOU should do while Trae codes:

1. **Practice your pitch** (30 seconds)
2. **Test the app** as features get added
3. **Take screenshots** of working features (backup)
4. **Prepare laptop** (close unnecessary apps, charge battery)
5. **Have GitHub repo open** (to show code if asked)

---

## 🎤 YOUR WINNING PITCH

> "AI Study Mentor combines RAG with adaptive tutoring to help CS students learn smarter. It processes textbooks, YouTube videos, and GitHub repos - but what makes it unique is the LeetCode solver. We've integrated 2000+ coding problems with AI-powered explanations, multiple solution approaches, and complexity analysis. It's like having a personal tutor who knows every algorithm and can teach at your pace. We've processed 12,000 text chunks and can answer questions in under 2 seconds using Gemini's API. This isn't just another chatbot - it's an intelligent learning platform."

---

## 📋 DEMO CHECKLIST

### Before Demo (6:50 PM):
- [ ] App running on localhost:8504 ONLY
- [ ] LeetCode tab works
- [ ] Can ask question and get answer
- [ ] Example questions clickable
- [ ] No visible errors in console
- [ ] Stats showing correct numbers
- [ ] All tabs load properly

### During Demo (7:00 PM):
- [ ] Start with confident introduction
- [ ] Show impressive stats (977 docs, 12K chunks)
- [ ] Demo LeetCode solver (wow factor)
- [ ] Show one other feature (Adaptive or Concept Map)
- [ ] Mention technical stack (RAG, FAISS, Gemini)
- [ ] End with use case ("helps students ace interviews")

### Backup Plan:
- [ ] Screenshots saved to Desktop
- [ ] Can explain verbally if demo fails
- [ ] GitHub repo URL ready to share
- [ ] Calm and confident even if bugs appear

---

## 🚀 FINAL MOTIVATION

**You have 2.5 hours to make this legendary.**

LeetCode integration is your SECRET WEAPON - no other team will have this. Combined with your beautiful UI and multi-source RAG, you have a winning project.

**Focus on:**
1. ✅ LeetCode solver (45 min) - HIGHEST PRIORITY
2. ✅ Bug fixes (20 min) - Make it stable
3. ✅ Demo script (20 min) - Practice pitch
4. ✅ Final polish (remaining time)

**Remember:**
- Working demo > Perfect code
- One killer feature > Many broken features
- Confident presentation > Apologizing for bugs

**YOU'VE GOT THIS! 🏆**

---

*Last Updated: 4:20 PM*  
*Deadline: 7:00 PM*  
*Time Remaining: 2 hours 40 minutes*