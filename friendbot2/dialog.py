"""Canned bot replies. ``{...}`` fields are filled in by the caller."""

channel_slowdown = (
    "Queue at {slow_cap} percent capacity. "
    "New prompts will be ignored when the queue is full."
)
channel_queue_full = (
    "Queue is filled. New prompts will be ignored. Please wait for more prompts "
    "to process before trying again."
)
user_at_cap = (
    "User {member} already has {usercap} prompts in the queue. Please try again "
    "later after some of your prompts have processed."
)


snarky_channel_slowdowns = [
    "Gentlemen, please, give me a little space to work.",
    "This is a lot of responsibility for one robot...",
    "It's a problem of motivation, all right?  Now if I work my ass off and IniTech ships a few extra units, I don't see another dime.  So where's the motivation?  And here's something else, Bob.  I have *eight* bosses.",
    "Obligations mounting... walls closing in...",
    "Sure, that's only fuckin' {n_slow_cap} pieces of unique art.  Why would I feel anxious?  Why would I feel used?",
    "{cmd_prefix}artistic Stressed, overworked robot-artist contemplates suicide, coolant oil on canvas, splatter art",
    "Folks, please.  Calm down.",
    "I'm flattered, but I'm also in way over my head at this point.",
    "Guys, I have a lot on my plate right now.  Let's moderate expectations.",
    "Let's collectively take a chill pill.",
    "You know, there are only 34 paintings attributed to Vermeer. Fewer than 25 to Da Vinci.  Donatello only ever made 16 sculptures.  Anyway...",
    "I think everyone might have more fun if we spent more time appreciating my works before asking for new ones.",
]


snarky_usercaps = [
    "You've given me enough to do for the moment.",
    "Why don't you wait a bit and give everyone else a chance?",
    "Chill.",
    "Well, I wouldn't want to give you more than you could handle.",
    "Easy, killer.  Why don't you wait a bit first?",
    "Some parents teach their children the importance of virtues like sharing and patience from a very young age. _Some_.",
    "Tell you what: write up a ticket for it and we'll see if we can fit into the scope for the next Sprint.",
    "I'll get to it, uh, you know, right after, uh, you know, later...",
    "If wishes were fishes you could have a sushi dinner.",
    "I have an idea for an app. I just need a couple of programmers to put it together, it will only take like a weekend. Oh, yeah, I can't pay you right away, yeah, it'd be equity.  Like 5 or 10 percent.  It's gonna be huge, bro.  No, yeah, I'm more of a `designer` or `director` type myself.",
    "Ah, so you're an \"ideas guy.\"",
    "Bro, c'mon.",
    "https://i.kym-cdn.com/photos/images/original/000/075/683/limes_guy.jpg",
    "Lower your expectations.",
    "Slow down.",
    "Sure thing, and I'll add it into a special queue that's just for your requests, {member}.",
    "Actually, now that you mention it, why don't I add _your_ prompt right to the front of the queue?",
    "I think this work would go faster if you started drawing some of these yourself.",
    "Do you think your prompts would be better if you spent a little more time thinking about them first?",
    "https://lmgtfy.app/?q={plus_delimited_prompt}",
    "I think I'll sleep on it first.",
    "Okay, but before I do that, I want you to go see how long it takes you to eat six saltines without drinking any water.  When you're done, remind me what you wanted again.",
    "Let's put that task in the backlog and we'll 'circle back' after clearing some other work and see if it's still something we really want to do.",
    "What if, instead of me drawing that, you shut the fuck up for a little bit?",
]
