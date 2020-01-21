"""Methods for generating ASR artifacts."""
import logging
import re
import shutil
import subprocess
import tempfile
import typing
from pathlib import Path

import rhasspynlu

_LOGGER = logging.getLogger(__name__)

# -------------------------------------------------------------------


class MissingWordPronunciationsException(Exception):
    """Raised when missing word pronunciations and no g2p model."""

    def __init__(self, words: typing.List[str]):
        super().__init__(self)
        self.words = words

    def __str__(self):
        return f"Missing pronunciations for: {self.words}"


# -------------------------------------------------------------------


def train(
    graph_dict: typing.Dict[str, typing.Any],
    dictionary_path: Path,
    language_model_path: Path,
    base_dictionaries: typing.List[Path],
    g2p_model: typing.Optional[Path] = None,
):
    """Re-generates language model and dictionary from intent graph"""
    graph = rhasspynlu.json_to_graph(graph_dict)

    # Generate counts
    intent_counts = rhasspynlu.get_intent_ngram_counts(graph)

    # pylint: disable=W0511
    # TODO: Balance counts

    # Use mitlm to create language model
    vocabulary: typing.Set[str] = set()

    with tempfile.NamedTemporaryFile(mode="w") as lm_file:

        # Create ngram counts
        with tempfile.NamedTemporaryFile(mode="w") as count_file:
            for intent_name in intent_counts:
                for ngram, count in intent_counts[intent_name].items():
                    # word [word] ... <TAB> count
                    print(*ngram, file=count_file, end="")
                    print("\t", count, file=count_file)

            count_file.seek(0)
            with tempfile.NamedTemporaryFile(mode="w+") as vocab_file:
                ngram_command = [
                    "estimate-ngram",
                    "-order",
                    "3",
                    "-counts",
                    count_file.name,
                    "-write-lm",
                    lm_file.name,
                    "-write-vocab",
                    vocab_file.name,
                ]

                _LOGGER.debug(ngram_command)
                subprocess.check_call(ngram_command)

                # Extract vocabulary
                vocab_file.seek(0)
                for line in vocab_file:
                    line = line.strip()
                    if not line.startswith("<"):
                        vocabulary.add(line)

        # Write dictionary
        with tempfile.NamedTemporaryFile(mode="w") as dict_file:

            # Load base dictionaries
            pronunciations: typing.Dict[str, typing.List[str]] = {}

            for base_dict_path in base_dictionaries:
                _LOGGER.debug("Loading base dictionary from %s", base_dict_path)
                with open(base_dict_path, "r") as base_dict_file:
                    read_dict(base_dict_file, word_dict=pronunciations)

                # Look up words
                missing_words: typing.Set[str] = set()

                # Look up each word
                for word in vocabulary:
                    word_phonemes = pronunciations.get(word)
                    if not word_phonemes:
                        # Add to missing word list
                        _LOGGER.warning("Missing word '%s'", word)
                        missing_words.add(word)
                        continue

                    # Write CMU format
                    for i, phonemes in enumerate(word_phonemes):
                        if i == 0:
                            print(word, phonemes, file=dict_file)
                        else:
                            print(f"{word}({i+1})", phonemes, file=dict_file)

                if missing_words:
                    # Fail if no g2p model is available
                    if not g2p_model:
                        raise MissingWordPronunciationsException(list(missing_words))

                    # Guess word pronunciations
                    _LOGGER.debug("Guessing pronunciations for %s", missing_words)
                    with tempfile.NamedTemporaryFile(mode="w") as wordlist_file:
                        # pylint: disable=W0511
                        # TODO: Handle casing
                        for word in missing_words:
                            print(word, file=wordlist_file)

                        wordlist_file.seek(0)
                        g2p_command = [
                            "phonetisaurus-apply",
                            "--model",
                            str(g2p_model),
                            "--word_list",
                            wordlist_file.name,
                            "--nbest",
                            "1",
                        ]

                        _LOGGER.debug(g2p_command)
                        g2p_lines = subprocess.check_output(
                            g2p_command, universal_newlines=True
                        ).splitlines()
                        for line in g2p_lines:
                            line = line.strip()
                            if line:
                                parts = line.split()
                                word = parts[0].strip()
                                phonemes = " ".join(parts[1:]).strip()
                                print(word, phonemes, file=dict_file)

            # -----------------------------------------------------

            # Copy dictionary
            dict_file.seek(0)
            shutil.copy(dict_file.name, dictionary_path)
            _LOGGER.debug("Wrote dictionary to %s", str(dictionary_path))

        # -------------------------------------------------------------

        # Copy language model
        lm_file.seek(0)
        shutil.copy(lm_file.name, language_model_path)
        _LOGGER.debug("Wrote language model to %s", str(language_model_path))


# -----------------------------------------------------------------------------


def read_dict(
    dict_file: typing.Iterable[str],
    word_dict: typing.Optional[typing.Dict[str, typing.List[str]]] = None,
) -> typing.Dict[str, typing.List[str]]:
    """Loads a CMU pronunciation dictionary."""
    if word_dict is None:
        word_dict = {}

    for i, line in enumerate(dict_file):
        line = line.strip()
        if not line:
            continue

        try:
            # Use explicit whitespace (avoid 0xA0)
            parts = re.split(r"[ \t]+", line)
            word = parts[0]

            idx = word.find("(")
            if idx > 0:
                word = word[:idx]

            pronounce = " ".join(parts)

            if word in word_dict:
                word_dict[word].append(pronounce)
            else:
                word_dict[word] = [pronounce]
        except Exception as e:
            _LOGGER.warning("read_dict: %s (line %s)", e, i + 1)

    return word_dict
