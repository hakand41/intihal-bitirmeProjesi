import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine_similarity
from sklearn.decomposition import TruncatedSVD
import difflib

def cosine_similarity_tfidf(doc1, doc2):
    """Calculate cosine similarity between two documents using TF-IDF."""
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([doc1, doc2])
    return sk_cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]


def jaccard_similarity(doc1, doc2):
    """Calculate Jaccard similarity between two documents."""
    set1 = set(doc1.split())
    set2 = set(doc2.split())
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union != 0 else 0


def ngram_overlap(doc1, doc2, n=3):
    """Calculate n-gram overlap between two documents."""
    def get_ngrams(text, n):
        return {text[i:i+n] for i in range(len(text) - n + 1)}

    doc1_ngrams = get_ngrams(doc1, n)
    doc2_ngrams = get_ngrams(doc2, n)

    intersection = len(doc1_ngrams & doc2_ngrams)
    union = len(doc1_ngrams | doc2_ngrams)
    return intersection / union if union != 0 else 0


def lsa_cosine_similarity(doc1, doc2, n_components=100):
    """Calculate LSA (Latent Semantic Analysis) cosine similarity between two documents."""
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([doc1, doc2])
    svd = TruncatedSVD(n_components=n_components)
    lsa_matrix = svd.fit_transform(tfidf_matrix)
    return sk_cosine_similarity(lsa_matrix[0:1], lsa_matrix[1:2])[0][0]


def longest_common_subsequence(doc1, doc2):
    """Calculate longest common subsequence (LCS) similarity between two documents."""
    seq_matcher = difflib.SequenceMatcher(None, doc1, doc2)
    return seq_matcher.ratio()


def ast_similarity(doc1, doc2):
    """Calculate AST (Abstract Syntax Tree) similarity between two documents.
    For now, this is just a placeholder function. AST analysis typically involves parsing
    code and building abstract syntax trees. You might want to use a package like 'ast' for Python code.
    """
    # Placeholder: Implement AST-based similarity if working with code.
    return 0

# Levenshtein mesafesi hesaplamak için fonksiyon
def levenshtein_distance(str1, str2):
    len_str1, len_str2 = len(str1), len(str2)
    dp = [[0] * (len_str2 + 1) for _ in range(len_str1 + 1)]
    
    for i in range(len_str1 + 1):
        for j in range(len_str2 + 1):
            if i == 0:
                dp[i][j] = j
            elif j == 0:
                dp[i][j] = i
            elif str1[i - 1] == str2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[len_str1][len_str2]

# Levenshtein benzerliğini hesaplama
def levenshtein_similarity(doc1, doc2):
    distance = levenshtein_distance(doc1, doc2)
    max_len = max(len(doc1), len(doc2))
    return 1 - (distance / max_len)
