# AI Influencer Identity Consistency Plan

## Objective
Create a reusable digital-human identity package capable of supporting tens or hundreds of videos while maintaining consistent identity, style, and production quality.

## Level 1: Character Bible
Create a single source-of-truth document containing immutable traits:
- Name
- Apparent age
- Face shape
- Eye shape and color
- Nose characteristics
- Mouth characteristics
- Skin tone
- Hair color and style
- Body type
- Personality
- Voice style
- Movement style
- Camera style

Never modify these characteristics without creating a new identity version.

## Level 2: Canonical Reference Set
Generate and curate 30–50 approved images.

Include:
- Front view
- Front-left
- Front-right
- Left profile
- Right profile
- Neutral expression
- Smile
- Explaining
- Thinking
- Listening

Keep constant:
- Face
- Hair
- Age appearance
- Skin tone

Allow variation:
- Clothing
- Pose
- Camera angle

Store in: identity/reference_set_v1/

## Level 3: Face-Lock Identity Dataset
Create a structured identity index containing:
- Character metadata
- Canonical image list
- Face description
- Hair description
- Eye description
- Voice information
- Version information

This becomes the permanent source of truth.

## Level 4: Fixed Background Library
Generate backgrounds once and never regenerate them.

Examples:
- library_v1
- office_v1
- podcast_v1
- executive_v1
- home_office_v1

Store in: identity/backgrounds/

Prefer compositing onto fixed backgrounds rather than regenerating them.

## Level 5: Wardrobe Library
Create approved wardrobe packs:
- WARDROBE_A
- WARDROBE_B
- WARDROBE_C
- WARDROBE_D

Each wardrobe should have:
- Reference images
- Description
- Usage rules

Store in: identity/wardrobes/

## Level 6: Identity-First Generation Workflow
Always generate content through the identity package.

Workflow:
Character Bible
→ Reference Set
→ Identity Dataset
→ Wardrobe Selection
→ Background Selection
→ Character Image Generation
→ Video Generation
→ Publishing

Never generate assets without referencing the identity package.

## Level 7: Scalable Digital-Human Asset Strategy
Treat the influencer as a reusable asset rather than a series of prompts.

Required assets:
- Character Bible
- Reference Set
- Identity Dataset
- Background Library
- Wardrobe Library
- Motion Library
- Voice Profile

Goals:
- Consistent identity across hundreds of videos
- Ability to swap generation providers
- Stable long-term brand identity
- Automated content production pipeline

The digital-human identity package is the core intellectual property of the influencer business.
