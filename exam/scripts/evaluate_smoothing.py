# Generated with an AI assistant
"""Evaluate one fixed popularity pseudo-count extension after failed recency weighting.

Score = personal qualified-airing count + 3 * training viewers / maximum viewers.
This retains strong personal habits while smoothing weak evidence toward popularity.
"""
from evaluate_recency import main


if __name__ == '__main__':
    main('smoothed')
