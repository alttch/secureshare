DELETE
FROM tokens
WHERE expires <= :d
