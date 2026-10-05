import type { Post } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { formatPrice } from "@/features/create/form";
import { Carousel } from "@/features/feed/Carousel";
import { initials, matchLabel, totalPrice } from "@/features/feed/format";
import { VotePanel } from "@/features/feed/VotePanel";
import { IconArrowUpRight, IconShield } from "@/ui/icons";

type Props = {
  post: Post;
  width: number;
  onVote: (post: Post, score: number, styleConfirm: boolean | null) => void;
  voting: boolean;
};

/** Card di un fit nel feed (prototipo, schermata Feed). */
export const PostCard = memo(function PostCard({ post, width, onVote, voting }: Props) {
  const name = post.author ? `@${post.author.nickname}` : "Fit anonimo";
  const match = matchLabel(post.vote.style_match);
  const total = totalPrice(post.items);

  return (
    <View style={styles.card} role="article" aria-label={`${name}, ${post.style.name}`}>
      <View style={styles.head}>
        <View style={[styles.avatar, { backgroundColor: post.style.tone }]} aria-hidden>
          <Text style={styles.avatarText}>{initials(post.author?.nickname) || "?"}</Text>
        </View>
        <View style={styles.headText}>
          {post.author && !post.is_own ? (
            <Pressable
              role="link"
              aria-label={`Apri il profilo di ${name}`}
              onPress={() => router.push({ pathname: "/user/[nickname]", params: { nickname: post.author!.nickname } })}
              hitSlop={6}
            >
              <Text style={styles.author} numberOfLines={1}>
                {name}
              </Text>
            </Pressable>
          ) : (
            <Text style={styles.author} numberOfLines={1}>
              {post.is_own ? `${name} · tu` : name}
            </Text>
          )}
          <View style={styles.styleRow}>
            <Text style={styles.styleName}>{post.style.name}</Text>
            {match ? (
              <>
                <Text style={styles.dim}>·</Text>
                <IconShield color={colors.accent} size={13} />
                <Text style={styles.dim}>{match}</Text>
              </>
            ) : null}
          </View>
        </View>
      </View>

      <Carousel post={post} width={width} authorLabel={name} />

      <VotePanel post={post} busy={voting} onVote={(score, confirm) => onVote(post, score, confirm)} />

      {post.caption ? (
        <Text style={styles.caption}>
          {post.author ? <Text style={styles.captionAuthor}>{name} </Text> : null}
          {post.caption}
        </Text>
      ) : null}

      {post.items.length > 0 ? (
        <View style={styles.items}>
          <View style={styles.itemsHead}>
            <Text style={styles.itemsKicker}>IL FIT</Text>
            {total ? <Text style={styles.itemsKicker}>TOTALE {total}</Text> : null}
          </View>
          {post.items.map((item) => {
            const url = item.link?.url;
            return (
              <View key={item.position} style={styles.item}>
                <View style={styles.itemText}>
                  <Text style={styles.brand} numberOfLines={1}>
                    {item.brand}
                  </Text>
                  <Text style={styles.itemName} numberOfLines={1}>
                    {item.name}
                  </Text>
                </View>
                {item.price_cents !== null ? <Text style={styles.price}>{formatPrice(item.price_cents)}</Text> : null}
                {url ? (
                  <Pressable
                    role="link"
                    aria-label={`Apri ${item.link?.domain ?? "il negozio"}`}
                    onPress={() => void WebBrowser.openBrowserAsync(url)}
                    style={styles.shop}
                  >
                    <IconArrowUpRight color={colors.text} />
                  </Pressable>
                ) : (
                  <View style={styles.shopSpacer} />
                )}
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  card: { borderBottomWidth: 1, borderBottomColor: colors.divider, paddingBottom: 20 },
  head: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 10, paddingHorizontal: spacing[4] },
  avatar: {
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 1,
    borderColor: "#3A3A40",
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { fontFamily: fonts.uiExtraBold, fontSize: 12, letterSpacing: 0.5, color: colors.text },
  headText: { flex: 1, minWidth: 0 },
  author: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.text },
  styleRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 },
  styleName: { fontFamily: fonts.display, fontSize: 14, color: colors.text },
  dim: { fontFamily: fonts.ui, fontSize: 12, color: colors.textSecondary },
  caption: {
    fontFamily: fonts.ui,
    fontSize: 14,
    lineHeight: 20,
    color: colors.text,
    paddingHorizontal: spacing[4],
    paddingTop: 14,
  },
  captionAuthor: { fontFamily: fonts.uiBold },
  items: {
    marginHorizontal: spacing[4],
    marginTop: spacing[3],
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: 16,
    overflow: "hidden",
  },
  itemsHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderSubtle,
  },
  itemsKicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.3, color: colors.textSecondary },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingLeft: 14,
    paddingRight: 4,
    paddingVertical: 6,
    borderTopWidth: 1,
    borderTopColor: "#161619",
  },
  itemText: { flex: 1, minWidth: 0 },
  brand: {
    fontFamily: fonts.uiBold,
    fontSize: 11,
    letterSpacing: 1.1,
    textTransform: "uppercase",
    color: colors.textSecondary,
  },
  itemName: { fontFamily: fonts.ui, fontSize: 14, color: colors.text, marginTop: 2 },
  price: { fontFamily: fonts.mono, fontSize: 13, color: colors.text },
  shop: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  shopSpacer: { width: 8 },
});
