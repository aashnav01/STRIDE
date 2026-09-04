# Stride

**AI-assisted early detection of osteoarthritis risk markers, for health workers in India's North Eastern Region.**

Built for Smart India Hackathon problem statement **SIH26004** (Ministry of Development of North Eastern Region).

A health worker records a short side-on walking video on an ordinary phone. Stride extracts 33 pose landmarks per frame, computes gait features, and returns a knee-osteoarthritis risk score with a severity grade, the reasons behind it, and a referral — offline, in her language.

---

## Why

Knee OA is common and under-screened across the Northeast. A community study in a Jorhat tea-garden population found **29.4% prevalence**, against **28.7% nationally**. Yet orthopaedic specialists and imaging are concentrated in a handful of cities, and few community-based studies exist for the region at all.

Stride is designed for the person who closes that gap: the **ASHA worker**, screening in a village, on a low-end Android, often with no network.

## What it does

| Requirement (SIH26004) | Implementation |
|---|---|
| AI-based OA risk analysis | Gradient-boosted model over 101 gait features + optional ST-GCN stream |
| Gait and posture assessment | MediaPipe pose → joint-angle, asymmetry, rhythm and variability features |
| Pain and mobility screening inputs | Five-item pain/stiffness/function questionnaire, WOMAC-derived |
| Preliminary risk + severity | Risk band (low / borderline / elevated) and severity grade |
| Digital patient record | Patient details, symptoms and result stored per screening |
| Offline data collection | IndexedDB-first writes; nothing waits on connectivity |
| Offline synchronisation | Queue drains to the server when a network appears; idempotent on client id |
| Multilingual interface | English, Assamese (অসমীয়া), Manipuri (মণিপুরী) |
| Preventive guidance | Joint care, activity, nutrition and lifestyle, by risk band |
| Analytics dashboard | Screening counts, risk distribution, per-village breakdown |
| Report generation | PDF and CSV export |

### Explainability

The score is not a black box. An Explainable Boosting Machine surrogate produces ranked, plain-language reasons, each measurement is shown against its cohort median, and the model's own limits ship with every result.

**Worse-knee detection.** Osteoarthritis is usually asymmetric. Stride identifies which knee is more affected by comparing per-side range of motion, and leads the report with it.

## Design

The interface is built from the **gamosa** — Assam's woven cloth, whose motifs (*pari*, *kumbha*, *kingkhap*, *phul*, *miri*) are woven by rural women from the same communities ASHA workers come from. The Assam ASHA uniform is a white drape with a green border, so a green thread runs through the cloth; Assam's tea motif — two leaves and a bud — sits in the border for the tea-garden workers this exists for.

Type is set in **Tiro Bangla** (a Bengali/Latin serif on traditional letterforms), **Hind Siliguri** (drawn for reading Assamese), and **Baloo Da 2**.

## Running it

**Backend**

```bash
cd backend
python -m venv venv && venv/Scripts/activate    # or: source venv/bin/activate
pip install -r requirements.txt

# no frame cap and full-resolution landmarks — a laptop has the memory
MAX_ANALYSIS_FRAMES=0 MAX_WIDTH=1280 uvicorn main:app --reload --port 8000
```

`MAX_ANALYSIS_FRAMES` (200) and `MAX_WIDTH` (512) default to values that fit
a 512 MB host. They exist only for constrained deployments; locally there is
no reason to throttle, and the analysis runs roughly ten times faster.

**Frontend**

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The service worker registers only in a production build. To exercise the offline path:

```bash
npm run build && npm run preview
```

then switch the network off mid-screening and back on to watch the queue drain.

## Deploying

See **[DEPLOY.md](DEPLOY.md)**. The two services need each other's public
URLs, which Render cannot supply automatically — `VITE_API_URL` is baked in
at build time and must be set before the frontend is built.

## Limits

This is a screening aid, **not a diagnosis**. Knee OA is diagnosed clinically and radiographically.

- Trained on 80 adults recorded with a fixed DSLR in one clinic. Phone-camera and field performance are untested.
- Walking speed separates the training groups almost perfectly; the model was trained with that dependence adversarially reduced, but it cannot be eliminated from this dataset.
- The healthy group averaged 43.7 years against 56.8 for patients.
- The pain questionnaire is a shortened screening adaptation of WOMAC, not the scored WOMAC instrument.
- **Assamese and Manipuri strings are a machine-assisted draft and need native-speaker review before real patient use.**
- **Patient data is not yet encrypted at rest and the API has no access control.** Do not point this at real patient records as it stands.

## Sources

- [Prevalence of primary knee OA in the tea-garden community of Jorhat, Assam](https://ijor.org/archive/volume/9/issue/1/article/7334)
- [Knee OA burden in rural India](https://pmc.ncbi.nlm.nih.gov/articles/PMC11633723/)
